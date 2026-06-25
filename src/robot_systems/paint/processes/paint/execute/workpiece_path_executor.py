from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Optional

import numpy as np

from src.engine.geometry.planar import (
    axis_equivalent_shift_degrees,
    nearest_axis_equivalent_degrees,
    rotate_xy,
    unwrap_degrees,
)
from src.applications.workpiece_editor.service.i_workpiece_path_executor import (
    IWorkpiecePathExecutor,
    WorkpieceProcessAction,
)
from src.engine.robot.path_preparation import IWorkpiecePathPreparationService
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintSimulationConfig,
)
from src.robot_systems.paint.processes.paint.execute.execution_plane import (
    get_execution_plane_strategy,
)
from src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts import (
    start_robot_motion_trace,
    write_execution_motion_trace,
    write_pivot_debug_dump,
    write_pivot_debug_plot,
)
from src.robot_systems.paint.processes.paint.execute.pivot_projection import (
    project_paint_motion_geometry_continuous,
    rebase_projected_paint_path_to_zero_start_rz,
)
from src.robot_systems.paint.timing import TimingRecorder, timed_block, timed_step, timing_session

_logger = logging.getLogger(__name__)

_STAGING_Z_OFFSET_MM = -10.0
_STAGING_PAINT_AXIS_OFFSET_MM = 10.0


def _elapsed_s(start: float) -> float:
    return perf_counter() - float(start)


def _path_length_mm(path):
    xyz = np.asarray([pose[:3] for pose in path], dtype=float)
    if len(xyz) < 2:
        return 0.0
    return float(np.linalg.norm(np.diff(xyz, axis=0), axis=1).sum())


def _planar_spacing_stats(
    path: list[list[float]],
    planar_indices: tuple[int, int],
) -> tuple[float, float, float]:
    """Return min/mean/max spacing in the active source plane."""
    if len(path) < 2:
        return 0.0, 0.0, 0.0
    planar_i, planar_j = planar_indices
    required_index = max(planar_i, planar_j)
    if any(len(pose) <= required_index for pose in path):
        return 0.0, 0.0, 0.0
    points = np.asarray([[float(pose[planar_i]), float(pose[planar_j])] for pose in path], dtype=float)
    lengths = np.linalg.norm(np.diff(points, axis=0), axis=1)
    positive = lengths[lengths > 1e-9]
    if len(positive) == 0:
        return 0.0, 0.0, 0.0
    return float(np.min(positive)), float(np.mean(positive)), float(np.max(positive))


def _camera_to_tcp_delta(
    x_offset: float,
    y_offset: float,
    current_rz: float,
    reference_rz: float = 0.0,
) -> tuple[float, float]:
    """Return the tool-frame TCP sweep delta between the reference and current pickup angles."""
    cur_x, cur_y = rotate_xy(x_offset, y_offset, current_rz)
    ref_x, ref_y = rotate_xy(x_offset, y_offset, reference_rz)
    return cur_x - ref_x, cur_y - ref_y


def _shift_path_rotation(path: list[list[float]], rotation_index: int, shift_degrees: float) -> list[list[float]]:
    """Apply a constant shift to one rotation component across a projected path."""
    if not path:
        return []
    shift = float(shift_degrees)
    shifted = [list(pose) for pose in path]
    if abs(shift) <= 1e-9:
        return shifted
    for pose in shifted:
        if len(pose) > rotation_index:
            pose[rotation_index] = float(pose[rotation_index]) + shift
    return shifted


def _diagnostics_with_command_rotation(
    diagnostics: list[dict[str, float | int]] | None,
    command_path: list[list[float]],
    rotation_index: int,
) -> list[dict[str, float | int]] | None:
    """Attach final robot-command rotation values to projection diagnostics."""
    if not diagnostics:
        return diagnostics
    adjusted: list[dict[str, float | int]] = []
    previous_rotation: float | None = None
    for index, item in enumerate(diagnostics):
        updated = dict(item)
        if index < len(command_path) and len(command_path[index]) > rotation_index:
            current_rotation = float(command_path[index][rotation_index])
            updated["command_rz"] = current_rotation
            updated["command_rotation_delta"] = (
                0.0 if previous_rotation is None else current_rotation - previous_rotation
            )
            previous_rotation = current_rotation
        adjusted.append(updated)
    return adjusted


def _paint_axis_staging_offset_pose(
    contact_pose: list[float],
    pivot_config: PaintSimulationConfig,
    *,
    z_offset_mm: float = _STAGING_Z_OFFSET_MM,
    paint_axis_offset_mm: float = _STAGING_PAINT_AXIS_OFFSET_MM,
) -> list[float]:
    """Return the pre-paint staging pose below and behind the first pivot contact."""
    offset_pose = list(contact_pose)
    if len(offset_pose) > 2:
        offset_pose[2] = float(offset_pose[2]) + float(z_offset_mm)

    try:
        axis_position = pivot_config.planar_axes.index(pivot_config.translation_axis)
    except ValueError:
        return offset_pose

    axis_index = pivot_config.planar_coordinate_indices[axis_position]
    if len(offset_pose) <= axis_index or abs(float(paint_axis_offset_mm)) <= 1e-9:
        return offset_pose

    offset_pose[axis_index] = (
        float(offset_pose[axis_index])
        - float(pivot_config.direction_sign) * float(paint_axis_offset_mm)
    )
    return offset_pose


def _projection_tool_anchor_xy(job: dict, pivot_config: PaintSimulationConfig) -> tuple[float, float] | None:
    """Return the selected tool/workpiece anchor used by pivot projection."""
    if tuple(pivot_config.source_planar_coordinate_indices) != (0, 1):
        return None
    pickup_xy = job.get("pickup_xy")
    if not pickup_xy or len(pickup_xy) < 2:
        return None
    try:
        return float(pickup_xy[0]), float(pickup_xy[1])
    except (TypeError, ValueError):
        return None


def _tcp_to_tool_local_xy(job: dict, pivot_config: PaintSimulationConfig) -> tuple[float, float] | None:
    """Return the local vector from configured robot TCP to selected tool point."""
    target_name = str(job.get("execution_target_point_name", "") or "").strip().lower()
    if not target_name or target_name == "camera":
        return None
    try:
        point_offset_x = float(job.get("execution_target_offset_x", 0.0) or 0.0)
        point_offset_y = float(job.get("execution_target_offset_y", 0.0) or 0.0)
        tcp_offset_x = float(pivot_config.camera_to_tcp_x_offset)
        tcp_offset_y = float(pivot_config.camera_to_tcp_y_offset)
    except (TypeError, ValueError):
        return None
    tcp_to_tool_x = point_offset_x - tcp_offset_x
    tcp_to_tool_y = point_offset_y - tcp_offset_y
    if abs(tcp_to_tool_x) <= 1e-9 and abs(tcp_to_tool_y) <= 1e-9:
        return None
    return tcp_to_tool_x, tcp_to_tool_y


def _pivot_source_path(job: dict, pivot_config: PaintSimulationConfig) -> list[list[float]]:
    """Return the path used as geometric source for pivot projection."""
    path = job.get("pivot_source_path") or job.get("execution_path") or []
    if isinstance(path, list):
        return path
    return [list(point) for point in path]


def _prepare_pivot_source_plan(
    plan: WorkpieceExecutionPlan,
    pivot_config: PaintSimulationConfig,
) -> WorkpieceExecutionPlan:
    """Attach the final paint-pivot source contour to each execution job.

    Path preparation owns pixel-to-mm conversion, contour smoothing, and final
    1 mm sampling. The paint executor consumes that final execution path directly
    as pivot source geometry; it does not resample or simplify the contour.
    """
    if not plan.execution_jobs:
        return plan

    prepared_jobs: list[dict] = []
    total_pivot_source_points = 0
    for job_index, job in enumerate(plan.execution_jobs, start=1):
        prepared_job = dict(job)
        source_path = [list(point) for point in (job.get("execution_path") or [])]
        pivot_source_path = [list(point) for point in source_path]
        min_spacing_mm, mean_spacing_mm, max_spacing_mm = _planar_spacing_stats(
            pivot_source_path,
            pivot_config.source_planar_coordinate_indices,
        )
        prepared_job["pivot_source_path"] = pivot_source_path
        prepared_job["pivot_pipeline"] = {
            "source": "execution_path",
            "source_points": len(source_path),
            "pivot_source_points": len(pivot_source_path),
            "min_spacing_mm": min_spacing_mm,
            "mean_spacing_mm": mean_spacing_mm,
            "max_spacing_mm": max_spacing_mm,
        }
        total_pivot_source_points += len(pivot_source_path)
        if source_path:
            _logger.info(
                "[PIVOT_PIPELINE] job=%d final_contour_source=%s source_pts=%d pivot_source_pts=%d actual_spacing[min=%.3f mean=%.3f max=%.3f]mm",
                job_index,
                prepared_job["pivot_pipeline"]["source"],
                len(source_path),
                len(pivot_source_path),
                min_spacing_mm,
                mean_spacing_mm,
                max_spacing_mm,
            )
        prepared_jobs.append(prepared_job)

    return WorkpieceExecutionPlan(
        workpiece=plan.workpiece,
        raw_paths=plan.raw_paths,
        prepared_paths=plan.prepared_paths,
        curve_paths=plan.curve_paths,
        sampled_paths=plan.sampled_paths,
        execution_jobs=prepared_jobs,
        total_spline_pts=total_pivot_source_points or plan.total_spline_pts,
        raw_pixel_paths=plan.raw_pixel_paths,
        raw_homography_paths=plan.raw_homography_paths,
    )


def _project_paint_motion_geometry_continuous(
    path: list[list[float]],
    pivot_pose: list[float],
    pivot_config: PaintSimulationConfig,
    *,
    anchor_xy: tuple[float, float] | None = None,
    source_rotation_deg: float = 0.0,
) -> tuple[list[list[float]], list[np.ndarray], list[dict[str, float | int]]]:
    if anchor_xy is None:
        return project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            pivot_config,
            source_rotation_deg=source_rotation_deg,
        )
    return project_paint_motion_geometry_continuous(
        path,
        pivot_pose,
        pivot_config,
        anchor_xy=anchor_xy,
        source_rotation_deg=source_rotation_deg,
    )


@dataclass(frozen=True)
class PickupToPivotPlan:
    """Concrete pickup and staging poses derived from one prepared execution plan."""
    pickup_approach_pose: list[float]
    pickup_pose: list[float]
    lift_pose: list[float]
    align_pose: list[float]
    stage_transition_poses: list[list[float]]
    staged_pose: list[float]
    change_plane_pose: list[float]
    paint_pivot_pose: list[float]
    source_rotation_deg: float = 0.0
    projected_source_path: list[list[float]] | None = None
    projected_pivot_path: list[list[float]] | None = None
    projected_snapshots: list[np.ndarray] | None = None
    projected_diagnostics: list[dict[str, float | int]] | None = None

def _normalize_pivot_config(
    *,
    motion_plane: str = "xy_z_rz",
    translation_axis: str = "x",
    pivot_side: str = "negative",
    translation_direction: str = "forward",
    apply_camera_to_tcp_for_pickup: bool = False,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
    rotation_direction_sign: float = 1.0,
) -> PaintSimulationConfig:
    """Normalize user-facing pivot settings into a validated simulation config."""
    rules = PaintSimulationConfig().rules
    default_plane = rules.default_motion_plane
    plane_key = str(motion_plane or default_plane).strip().lower()
    axis_key = str(translation_axis or "x").strip().lower()
    side_key = str(pivot_side or rules.default_paint_side).strip().lower()
    direction_key = str(translation_direction or rules.default_translation_direction).strip().lower()
    plane_spec = rules.motion_plane_specs.get(plane_key, rules.motion_plane_specs[default_plane])
    valid_axes = tuple(plane_spec.axis_offsets_deg.keys())
    return PaintSimulationConfig(
        motion_plane=plane_key if plane_key in rules.motion_plane_specs else default_plane,
        translation_axis=axis_key if axis_key in valid_axes else valid_axes[0],
        paint_side=side_key if side_key in rules.side_signs else rules.default_paint_side,
        translation_direction=(
            direction_key if direction_key in rules.translation_direction_signs else rules.default_translation_direction
        ),
        apply_camera_to_tcp_for_pickup=bool(apply_camera_to_tcp_for_pickup),
        camera_to_tcp_x_offset=float(camera_to_tcp_x_offset),
        camera_to_tcp_y_offset=float(camera_to_tcp_y_offset),
        rotation_direction_sign=-1.0 if float(rotation_direction_sign) < 0.0 else 1.0,
    )


def _xz_ry_projection_rotation_sign(motion_plane: str, mirror_execution_rotation: bool) -> float:
    """Return the planar rotation sign used during projection, before command generation."""
    if motion_plane == "xz_y_ry" and mirror_execution_rotation:
        return -1.0
    return 1.0


class PaintWorkpiecePathExecutor(IWorkpiecePathExecutor):
    """Execute prepared paint paths, including pickup, staging, and pivot painting."""
    def __init__(
        self,
        robot_service,
        path_preparation_service: Optional[IWorkpiecePathPreparationService] = None,
        base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
        pickup_base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None,
        post_execute_callback: Optional[Callable[[], bool]] = None,
        robot_config_provider: Optional[Callable[[], object]] = None,
        vacuum_pump=None,
        enable_vacuum_pump: bool = True,
        pickup_tool: int = 0,
        pickup_user: int = 0,
        pickup_z_mm: float | None = None,
        debug_dump_dir: str | None = None,
        pivot_motion_plane: str = "xy_z_rz",
        pivot_translation_axis: str = "x",
        pivot_side: str = "negative",
        pivot_translation_direction: str = "forward",
        flip_xz_ry_execution_rotation_direction: bool = False,
        mirror_xz_ry_pickup_handoff: bool = False,
        enable_xz_ry_preflight: bool = True,
        xz_ry_preflight_max_checks: int = 8,
        apply_camera_to_tcp_for_pickup: bool = False,
        camera_to_tcp_x_offset: float = 0.0,
        camera_to_tcp_y_offset: float = 0.0,
    ) -> None:
        """Store robot dependencies and initialize the pivot/pickup execution configuration."""
        self._robot_service = robot_service
        self._path_preparation_service = path_preparation_service
        self._base_position_provider = base_position_provider
        self._pickup_base_position_provider = pickup_base_position_provider or base_position_provider
        self._post_execute_callback = post_execute_callback
        self._robot_config_provider = robot_config_provider
        self._vacuum_pump = vacuum_pump
        self._enable_vacuum_pump = bool(enable_vacuum_pump)
        self._pickup_tool = int(pickup_tool)
        self._pickup_user = int(pickup_user)
        self._pickup_z_mm = None if pickup_z_mm is None else float(pickup_z_mm)
        self._pickup_safety_z_min_mm = 100.0
        self._debug_dump_dir = debug_dump_dir
        self._last_execution_plan: WorkpieceExecutionPlan | None = None
        self._last_pickup_plan: PickupToPivotPlan | None = None
        self._pending_stage_pose: list[float] | None = None
        self._flip_xz_ry_execution_rotation_direction = bool(flip_xz_ry_execution_rotation_direction)
        self._mirror_xz_ry_pickup_handoff = bool(mirror_xz_ry_pickup_handoff)
        self._enable_xz_ry_preflight = bool(enable_xz_ry_preflight)
        self._xz_ry_preflight_max_checks = max(1, int(xz_ry_preflight_max_checks))
        self._pivot_config = _normalize_pivot_config(
            motion_plane=pivot_motion_plane,
            translation_axis=pivot_translation_axis,
            pivot_side=pivot_side,
            translation_direction=pivot_translation_direction,
            apply_camera_to_tcp_for_pickup=apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=camera_to_tcp_y_offset,
            rotation_direction_sign=_xz_ry_projection_rotation_sign(
                pivot_motion_plane,
                self._flip_xz_ry_execution_rotation_direction,
            ),
        )
        self._pickup_pivot_config = _normalize_pivot_config(
            motion_plane="xy_z_rz",
            translation_axis=pivot_translation_axis,
            pivot_side=pivot_side,
            translation_direction=pivot_translation_direction,
            apply_camera_to_tcp_for_pickup=apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=camera_to_tcp_y_offset,
        )
        self._pivot_strategy = get_execution_plane_strategy(self._pivot_config.motion_plane)
        self._last_process_start_rz: float | None = None
        self._last_process_end_pose: list[float] | None = None

    def _validate_xz_ry_pivot_path(self, pivot_path: list[list[float]]) -> tuple[bool, str]:
        """Preflight sampled pivot-path segments for xz/ry mode only.

        This is intentionally narrow so the established xy/rz flow is unchanged.
        """
        if not self._pivot_strategy.requires_reachability_preflight:
            return True, ""
        if not self._enable_xz_ry_preflight:
            _logger.info("[PIVOT_PATH] xz/ry preflight skipped: disabled by configuration")
            return True, ""
        if self._robot_service is None or len(pivot_path) < 2:
            return True, ""

        # Sample a handful of segments across the full path so we can fail early
        # with a concrete offending segment instead of waiting for execute_path().
        max_checks = self._xz_ry_preflight_max_checks
        last_index = len(pivot_path) - 1
        sampled_indices = sorted(
            {
                0,
                last_index,
                *(
                    int(round(i * last_index / max_checks))
                    for i in range(1, max_checks)
                ),
            }
        )

        current_start = list(pivot_path[sampled_indices[0]])
        for waypoint_index in sampled_indices[1:]:
            target_pose = list(pivot_path[waypoint_index])
            result = self._robot_service.validate_pose(
                current_start,
                target_pose,
                tool=self._pickup_tool,
                user=self._pickup_user,
            )
            if result.get("supported") is False:
                _logger.info(
                    "[PIVOT_PATH] xz/ry preflight skipped: reachability validation not supported"
                )
                return True, ""
            if not bool(result.get("reachable")):
                reason = str(result.get("reason") or result.get("error") or "unreachable")
                _logger.warning(
                    "[PIVOT_PATH] xz/ry preflight failed at sampled waypoint %d/%d: "
                    "start=%s target=%s reason=%s result=%s",
                    waypoint_index,
                    len(pivot_path) - 1,
                    [round(float(v), 3) for v in current_start[:6]],
                    [round(float(v), 3) for v in target_pose[:6]],
                    reason,
                    result,
                )
                return False, (
                    "Pickup succeeded, but xz/ry pivot path is unreachable before execution "
                    f"(sampled waypoint {waypoint_index + 1}/{len(pivot_path)}, reason={reason})"
                )
            current_start = target_pose

        return True, ""

    def _execute_paint_trajectory_with_optional_trace(
            self,
            *,
            command_pivot_path: list[list[float]],
            vel: float,
            acc: float,
            pivot_pose: list[float] | None,
            pattern_type: str,
            stage: str,
            tcp_to_tool_local_xy: tuple[float, float] | None = None,
    ):
        """Execute a paint trajectory and optionally write commanded-vs-actual samples."""
        trace = None
        if (
                bool(getattr(PAINT_PROCESS_CONFIG, "enable_execution_motion_trace", False))
                and self._robot_service is not None
        ):
            trace = start_robot_motion_trace(
                get_pose=self._robot_service.get_current_position,
                sample_period_s=float(
                    getattr(PAINT_PROCESS_CONFIG, "execution_motion_trace_sample_period_s", 0.05)
                ),
            )
        try:
            return self._robot_service.execute_trajectory(
                command_pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
        finally:
            if trace is not None:
                samples = trace.stop()
                write_execution_motion_trace(
                    debug_dump_dir=self._debug_dump_dir,
                    pivot_config=self._pivot_config,
                    commanded_path=command_pivot_path,
                    actual_samples=samples,
                    pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                    pattern_type=pattern_type,
                    stage=stage,
                    tcp_to_tool_local_xy=tcp_to_tool_local_xy,
                )

    def prepare_workpiece_preview(self, workpiece: dict, skip_debug_plot: bool = False) -> WorkpieceExecutionPlan:
        """Build and cache the execution plan for a paint workpiece."""
        if self._path_preparation_service is None:
            raise RuntimeError("Path preparation service is not available")
        generic_plan = self._path_preparation_service.build_execution_plan(workpiece, skip_debug_plot=skip_debug_plot)
        self._last_execution_plan = _prepare_pivot_source_plan(generic_plan, self._pivot_config)
        # self._write_path_shape_comparison_debug(self._last_execution_plan)
        return self._last_execution_plan

    def get_last_execution_plan(self) -> WorkpieceExecutionPlan | None:
        """Return the last paint preview plan prepared by this executor."""
        return self._last_execution_plan

    def _write_path_shape_comparison_debug(self, plan: WorkpieceExecutionPlan) -> None:
        if not self._debug_dump_dir:
            return
        try:
            from src.engine.robot.path_interpolation.new_interpolation.debug_plotting import (
                write_path_shape_comparison_debug,
            )

            result = write_path_shape_comparison_debug(
                raw_paths=plan.raw_paths,
                sampled_paths=plan.sampled_paths,
                execution_paths=plan.execution_paths(),
                save_dir=self._debug_dump_dir,
            )
            if result:
                _logger.info("[EXECUTE] Saved path shape comparison debug artifacts: %s", result)
        except Exception:
            _logger.debug("[EXECUTE] Failed to write path shape comparison debug artifacts", exc_info=True)

    def _refresh_runtime_config(self) -> None:
        """Refresh robot-dependent pickup settings from the latest robot configuration."""
        if self._robot_config_provider is None:
            return
        try:
            robot_config = self._robot_config_provider()
        except Exception:
            _logger.debug("[PICKUP] Failed to refresh robot config", exc_info=True)
            return
        if robot_config is None:
            return
        self._pickup_tool = int(getattr(robot_config, "robot_tool", self._pickup_tool))
        self._pickup_user = int(getattr(robot_config, "robot_user", self._pickup_user))
        try:
            self._pickup_safety_z_min_mm = float(getattr(getattr(robot_config, "safety_limits", None), "z_min", self._pickup_safety_z_min_mm))
        except Exception:
            pass
        self._pivot_config = _normalize_pivot_config(
            motion_plane=self._pivot_config.motion_plane,
            translation_axis=self._pivot_config.translation_axis,
            pivot_side=self._pivot_config.paint_side,
            translation_direction=self._pivot_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._pivot_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._pivot_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._pivot_config.camera_to_tcp_y_offset)),
            rotation_direction_sign=_xz_ry_projection_rotation_sign(
                self._pivot_config.motion_plane,
                self._flip_xz_ry_execution_rotation_direction,
            ),
        )
        self._pickup_pivot_config = _normalize_pivot_config(
            motion_plane="xy_z_rz",
            translation_axis=self._pickup_pivot_config.translation_axis,
            pivot_side=self._pickup_pivot_config.paint_side,
            translation_direction=self._pickup_pivot_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._pickup_pivot_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._pickup_pivot_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._pickup_pivot_config.camera_to_tcp_y_offset)),
        )
        self._pivot_strategy = get_execution_plane_strategy(self._pivot_config.motion_plane)

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        """Report the execution modes supported by the paint executor."""
        return ("pivot_path",)

    def get_process_actions(self) -> tuple[WorkpieceProcessAction, ...]:
        """Expose the paint process as one editor-facing action."""
        return (
            WorkpieceProcessAction(
                action_id="paint_process",
                label="Approve Paint Process",
                requires_projected_path_plot=True,
            ),
        )

    def execute_process_action(
        self,
        execution_plan: WorkpieceExecutionPlan,
        action_id: str,
    ) -> tuple[bool, str]:
        """Execute the requested paint process action."""
        action_id = str(action_id or "").strip().lower()
        if action_id != "paint_process":
            return False, f"Unsupported paint process action: {action_id}"
        return self.execute_pickup_and_paint(execution_plan)

    def _resolve_base_position(self) -> Optional[list[float]]:
        """Resolve the configured pivot/base pose used to project paint motion."""
        provider = self._base_position_provider
        if provider is None:
            return None
        try:
            position = provider()
        except Exception:
            _logger.debug("PaintWorkpiecePathExecutor: base position provider failed", exc_info=True)
            return None
        if not position or len(position) < 3:
            return None
        try:
            return [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None

    def _apply_pivot_offset(self, pivot_pose: list[float] | None, offset_mm: float) -> list[float] | None:
        """Apply the editor-configured pivot offset in the active pivot plane."""
        if pivot_pose is None:
            return None
        try:
            offset_value = float(offset_mm or 0.0)
        except (TypeError, ValueError):
            offset_value = 0.0
        adjusted_pose = list(pivot_pose)
        if abs(offset_value) <= 1e-9:
            return adjusted_pose
        target_index = self._pivot_strategy.pivot_offset_position_index
        while len(adjusted_pose) <= target_index:
            adjusted_pose.append(0.0)
        adjusted_pose[target_index] = float(adjusted_pose[target_index]) + offset_value
        return adjusted_pose

    @staticmethod
    def _resolve_pivot_offset_mm(job: dict | None, execution_plan: WorkpieceExecutionPlan | None = None) -> float:
        """Resolve the persisted pivot-offset setting from job or workpiece data."""
        if job is not None:
            try:
                return float(job.get("pivot_offset_mm", 0.0) or 0.0)
            except (TypeError, ValueError):
                pass
        if execution_plan is not None:
            try:
                return float((execution_plan.workpiece or {}).get("offset", 0.0) or 0.0)
            except (AttributeError, TypeError, ValueError):
                pass
        return 0.0

    def _resolve_pickup_base_position(self) -> Optional[list[float]]:
        """Resolve the pickup/staging base pose used for XY/RZ pickup alignment."""
        provider = self._pickup_base_position_provider
        if provider is None:
            return None
        try:
            position = provider()
        except Exception:
            _logger.debug("PaintWorkpiecePathExecutor: pickup base position provider failed", exc_info=True)
            return None
        if not position or len(position) < 3:
            return None
        try:
            return [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None

    def get_pivot_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        """Project preview center paths for each prepared execution job around the pivot pose."""
        self._refresh_runtime_config()
        base_pivot_pose = self._resolve_base_position()
        if base_pivot_pose is None or len(base_pivot_pose) < 3:
            return [], base_pivot_pose
        preview_pickup_plan = self._build_pickup_and_stage_poses(execution_plan)
        paths = []
        last_pivot_pose = list(base_pivot_pose)
        for job in execution_plan.execution_jobs:
            source_path = _pivot_source_path(job, self._pivot_config)
            if not source_path:
                continue
            pivot_pose = self._apply_pivot_offset(
                base_pivot_pose,
                self._resolve_pivot_offset_mm(job, execution_plan),
            )
            if pivot_pose is None or len(pivot_pose) < 3:
                continue
            last_pivot_pose = list(pivot_pose)
            anchor_xy = _projection_tool_anchor_xy(job, self._pivot_config)
            center_path, _, diagnostics = _project_paint_motion_geometry_continuous(
                source_path,
                pivot_pose,
                self._pivot_config,
                anchor_xy=anchor_xy,
                source_rotation_deg=(
                    float(preview_pickup_plan.source_rotation_deg)
                    if preview_pickup_plan is not None else 0.0
                ),
            )
            center_path = self._align_preview_path_to_pickup_plan(center_path, preview_pickup_plan)
            center_path = self._pivot_execution_command_path(center_path, pickup_plan=preview_pickup_plan)
            # self._write_pivot_debug_dump(
            #     source_path=source_path,
            #     pivot_path=center_path,
            #     diagnostics=diagnostics,
            #     pivot_pose=list(pivot_pose),
            #     pattern_type=str(job.get("pattern_type", "Path")),
            #     stage="preview",
            # )
            paths.append(center_path)
        return paths, last_pivot_pose

    def get_pivot_motion_preview(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        """Return per-step projected shape snapshots for pivot motion preview/plotting."""
        self._refresh_runtime_config()
        base_pivot_pose = self._resolve_base_position()
        if base_pivot_pose is None or len(base_pivot_pose) < 3:
            return [], base_pivot_pose
        preview_pickup_plan = self._build_pickup_and_stage_poses(execution_plan)
        motion = []
        last_pivot_pose = list(base_pivot_pose)
        for job in execution_plan.execution_jobs:
            source_path = _pivot_source_path(job, self._pivot_config)
            if not source_path:
                continue
            pivot_pose = self._apply_pivot_offset(
                base_pivot_pose,
                self._resolve_pivot_offset_mm(job, execution_plan),
            )
            if pivot_pose is None or len(pivot_pose) < 3:
                continue
            last_pivot_pose = list(pivot_pose)
            anchor_xy = _projection_tool_anchor_xy(job, self._pivot_config)
            _, snapshots, _ = _project_paint_motion_geometry_continuous(
                source_path,
                pivot_pose,
                self._pivot_config,
                anchor_xy=anchor_xy,
                source_rotation_deg=(
                    float(preview_pickup_plan.source_rotation_deg)
                    if preview_pickup_plan is not None else 0.0
                ),
            )
            motion.append(snapshots)
        return motion, last_pivot_pose


    def _build_pivot_execution_path(
        self,
        spline: list[list[float]],
        *,
        pivot_offset_mm: float = 0.0,
        align_start_to_zero_rz: bool = False,
        anchor_xy: tuple[float, float] | None = None,
        source_rotation_deg: float = 0.0,
    ) -> tuple[
        list[list[float]],
        list[np.ndarray] | None,
        list[dict[str, float | int]] | None,
        list[float] | None,
    ] | None:
        """Project one prepared spline into the real pivot execution trajectory."""
        with timed_block(_logger, "pivot_path_prepare", label="resolve_base_and_offset"):
            pivot_pose = self._apply_pivot_offset(self._resolve_base_position(), pivot_offset_mm)
        if pivot_pose is None or len(pivot_pose) < 3:
            return None
        with timed_block(_logger, "pivot_path_prepare", label="project_execution_path"):
            pivot_path, snapshots, diagnostics = _project_paint_motion_geometry_continuous(
                spline,
                pivot_pose,
                self._pivot_config,
                anchor_xy=anchor_xy,
                source_rotation_deg=source_rotation_deg,
            )
        _logger.debug("Simulated pivot path has %d points", len(pivot_path))
        if align_start_to_zero_rz:
            with timed_block(_logger, "pivot_path_prepare", label="rebase_start_rotation"):
                pivot_path = rebase_projected_paint_path_to_zero_start_rz(
                    pivot_path,
                    self._pivot_config,
                )
        return pivot_path, snapshots, diagnostics, list(pivot_pose)

    def execute_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        """Execute a prepared plan by projecting each path into pivot motion and sending it to the robot."""
        jobs = execution_plan.execution_jobs
        if not jobs:
            return False, "No prepared process paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        mode = str(mode or "continuous").strip().lower()
        if mode != "pivot_path":
            return False, f"Unsupported paint execution mode: {mode}"

        total_waypoints = 0
        for job in jobs:
            spline = _pivot_source_path(job, self._pivot_config)
            _logger.debug(f"Execution path before build_pivot_execution_path: {len(spline)}")
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            pivot_offset_mm = self._resolve_pivot_offset_mm(job, execution_plan)
            tcp_to_tool_local_xy = _tcp_to_tool_local_xy(job, self._pivot_config)

            if not spline:
                continue

            pivot_pose = self._apply_pivot_offset(self._resolve_base_position(), pivot_offset_mm)
            if pivot_pose is None or len(pivot_pose) < 3:
                return False, "Pivot-path execution requires a valid base/pivot position"
            anchor_xy = _projection_tool_anchor_xy(job, self._pivot_config)
            pivot_path, _, diagnostics = _project_paint_motion_geometry_continuous(
                spline,
                pivot_pose,
                self._pivot_config,
                anchor_xy=anchor_xy,
            )
            if not pivot_path:
                return False, "Pivot-path execution requires a valid base/pivot position"
            _logger.debug(f"Pivot path after build_pivot_execution_path: {len(pivot_path)}")
            command_pivot_path = self._pivot_execution_command_path(pivot_path)

            # self._write_pivot_debug_dump(
            #     source_path=spline,
            #     pivot_path=command_pivot_path,
            #     diagnostics=diagnostics,
            #     pivot_pose=pivot_pose,
            #     pattern_type=pattern_type,
            #     stage="execute",
            # )
            result = self._execute_paint_trajectory_with_optional_trace(
                command_pivot_path=command_pivot_path,
                vel=vel,
                acc=acc,
                pivot_pose=pivot_pose,
                pattern_type=pattern_type,
                stage="execute",
                tcp_to_tool_local_xy=tcp_to_tool_local_xy,
            )
            if result not in (0, True, None):
                return False, f"{pattern_type} pivot-path execution failed with code {result}"
            total_waypoints += len(command_pivot_path)
            _logger.info(
                "[EXECUTE] [RUN PROCESS] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
                len(command_pivot_path), mode, vel, acc,
            )

        if self._post_execute_callback is not None:
            try:
                moved = bool(self._post_execute_callback())
            except Exception:
                _logger.exception("[EXECUTE] Post-execute callback failed")
                return False, "Execution finished, but return-to-calibration failed"
            if not moved:
                return False, "Execution finished, but return-to-calibration failed"
            _logger.info("[EXECUTE] Returned to post-execution position")

        return True, (
            f"Executed {len(jobs)} path(s), "
            f"{total_waypoints} waypoints in {mode} mode"
        )

    def _build_pickup_and_stage_poses(
            self,
            execution_plan: WorkpieceExecutionPlan,
    ) -> PickupToPivotPlan | None:
        """Build XY/RZ pickup poses and the first staged pose for the active paint process plane."""
        jobs = execution_plan.execution_jobs
        with timed_block(_logger, "pickup_plan_build", label="refresh_runtime_config"):
            self._refresh_runtime_config()
        if not jobs:
            return None

        with timed_block(_logger, "pickup_plan_build", label="resolve_pickup_base_position"):
            pickup_pivot_pose = self._resolve_pickup_base_position()
        _logger.debug(f"pickup_pivot_pose -> {pickup_pivot_pose}")

        with timed_block(_logger, "pickup_plan_build", label="resolve_paint_base_position"):
            paint_pivot_pose = self._resolve_base_position()
        _logger.debug(f"paint_pivot_pose -> {paint_pivot_pose}")

        if pickup_pivot_pose is None or len(pickup_pivot_pose) < 3:
            return None
        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        source_path = _pivot_source_path(jobs[0], self._pivot_config)
        if not source_path:
            return None

        pickup_xy = jobs[0].get("pickup_xy")
        if not pickup_xy or len(pickup_xy) < 2:
            return None

        pickup_centroid_x = float(pickup_xy[0])
        pickup_centroid_y = float(pickup_xy[1])

        anchor_xy = _projection_tool_anchor_xy(jobs[0], self._pivot_config)

        pivot_offset_mm = self._resolve_pivot_offset_mm(jobs[0], execution_plan)

        paint_pivot_pose = self._apply_pivot_offset(paint_pivot_pose, pivot_offset_mm)

        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        with timed_block(_logger, "pickup_plan_build", label="project_initial_pivot_path"):
            projected_pivot_path, projected_snapshots, projected_diagnostics = _project_paint_motion_geometry_continuous(
                source_path,
                paint_pivot_pose,
                self._pivot_config,
                anchor_xy=anchor_xy,
            )

        if not projected_pivot_path:
            return None

        first_pivot_pose = list(projected_pivot_path[0])

        _logger.debug(f"first_pivot_pose -> {first_pivot_pose}")
        if anchor_xy is not None and len(source_path[0]) >= 2 and len(first_pivot_pose) >= 3:
            source_planar_i, source_planar_j = self._pivot_config.source_planar_coordinate_indices
            planar_i, planar_j = self._pivot_config.planar_coordinate_indices
            source_first = np.asarray(
                [
                    float(source_path[0][source_planar_i]),
                    float(source_path[0][source_planar_j]),
                ],
                dtype=float,
            )
            source_anchor = np.asarray([float(anchor_xy[0]), float(anchor_xy[1])], dtype=float)
            source_offset = source_first - source_anchor
            command_offset = np.asarray(
                [
                    float(first_pivot_pose[planar_i]) - float(paint_pivot_pose[planar_i]),
                    float(first_pivot_pose[planar_j]) - float(paint_pivot_pose[planar_j]),
                ],
                dtype=float,
            )
            _logger.info(
                "[PICKUP] pivot anchor offset: source_first=(%.3f, %.3f) source_anchor=(%.3f, %.3f) "
                "source_first_minus_anchor=(%.3f, %.3f) command_tcp_minus_pivot_%s%s=(%.3f, %.3f)",
                float(source_first[0]),
                float(source_first[1]),
                float(source_anchor[0]),
                float(source_anchor[1]),
                float(source_offset[0]),
                float(source_offset[1]),
                self._pivot_config.planar_axes[0],
                self._pivot_config.planar_axes[1],
                float(command_offset[0]),
                float(command_offset[1]),
            )
        pickup_target_point_name = str(
            jobs[0].get("pickup_target_point_name", "") or ""
        ).strip().lower()
        workpiece_height_mm = float(jobs[0].get("workpiece_height_mm", 0.0) or 0.0)
        pickup_rx = float(pickup_pivot_pose[3]) if len(pickup_pivot_pose) >= 4 else 180.0
        pickup_ry = float(pickup_pivot_pose[4]) if len(pickup_pivot_pose) >= 5 else 0.0

        pickup_z = self._pickup_z_mm
        if pickup_z is None:
            pickup_z = self._pickup_safety_z_min_mm + workpiece_height_mm + PAINT_PROCESS_CONFIG.pickup_contact_offset_mm

        pickup_rz = float(jobs[0].get("pickup_rz", 0.0))

        pickup_rz_source = "execution_plan"
        # Modern path preparation resolves pickup_xy through the selected target
        # point already. Keep the legacy manual camera-to-TCP offset only for
        # older plans that do not declare a pickup target point.
        should_apply_tcp_offset = (
            bool(self._pivot_config.apply_camera_to_tcp_for_pickup)
            and not pickup_target_point_name
        )
        if should_apply_tcp_offset:
            pickup_tcp_dx, pickup_tcp_dy = _camera_to_tcp_delta(
                self._pivot_config.camera_to_tcp_x_offset,
                self._pivot_config.camera_to_tcp_y_offset,
                pickup_rz,
            )
        else:
            pickup_tcp_dx, pickup_tcp_dy = 0.0, 0.0
        _logger.info(
            "[PICKUP] pickup_xy=(%.3f, %.3f) pickup_rz=%.3f pickup_rz_source=%s pickup_target=%s workpiece_height=%.3f pickup_z=%.3f safety_z_min=%.3f apply_tcp_offset=%s configured_tcp_offset=(%.3f, %.3f) rotated_tcp_offset=(%.3f, %.3f)",
            pickup_centroid_x,
            pickup_centroid_y,
            pickup_rz,
            pickup_rz_source,
            pickup_target_point_name or "camera",
            workpiece_height_mm,
            float(pickup_z),
            self._pickup_safety_z_min_mm,
            should_apply_tcp_offset,
            self._pivot_config.camera_to_tcp_x_offset,
            self._pivot_config.camera_to_tcp_y_offset,
            pickup_tcp_dx,
            pickup_tcp_dy,
        )
        pickup_approach_z = float(pickup_z) + PAINT_PROCESS_CONFIG.pickup_approach_offset_mm
        pickup_approach_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            pickup_approach_z,
            pickup_rx,
            pickup_ry,
            pickup_rz,
        ]
        pickup_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            float(pickup_z),
            pickup_rx,
            pickup_ry,
            pickup_rz,
        ]

        align_rx = pickup_rx
        align_ry = pickup_ry
        pickup_reference_rz = float(
            jobs[0].get(
                "pickup_reference_rz",
                float(pickup_pivot_pose[5]) if len(pickup_pivot_pose) >= 6 else 0.0,
            )
        )
        align_rz = pickup_reference_rz
        source_rotation_deg = unwrap_degrees(float(pickup_rz), float(align_rz)) - float(pickup_rz)
        if abs(source_rotation_deg) > 1e-9:
            with timed_block(_logger, "pickup_plan_build", label="project_carried_rotation_path"):
                projected_pivot_path, projected_snapshots, projected_diagnostics = _project_paint_motion_geometry_continuous(
                    source_path,
                    paint_pivot_pose,
                    self._pivot_config,
                    anchor_xy=anchor_xy,
                    source_rotation_deg=source_rotation_deg,
                )
            if not projected_pivot_path:
                return None
            first_pivot_pose = list(projected_pivot_path[0])
            _logger.info(
                "[PICKUP] carried source rotation applied to pivot geometry: pickup_rz=%.3f align_rz=%.3f source_rotation_deg=%.3f first_pivot=%s",
                float(pickup_rz),
                float(align_rz),
                float(source_rotation_deg),
                [round(float(v), 3) for v in first_pivot_pose[:6]],
            )
        if self._pivot_config.motion_plane == "xz_y_ry":
            _logger.info(
                "[PICKUP] xz/ry handoff: mirrored=%s pickup_rz=%.3f first_pivot_ry=%.3f paint_reference_ry=%.3f align_rz=%.3f",
                self._mirror_xz_ry_pickup_handoff,
                pickup_rz,
                float(first_pivot_pose[4]) if len(first_pivot_pose) >= 5 else pickup_ry,
                float(paint_pivot_pose[4]) if len(paint_pivot_pose) >= 5 else pickup_ry,
                align_rz,
            )

        align_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            pickup_approach_z,
            align_rx,
            align_ry,
            align_rz,
        ]

        change_plane_pose = [
            pickup_centroid_x - pickup_tcp_dx,
            pickup_centroid_y - pickup_tcp_dy,
            float(pickup_approach_z),
            float(paint_pivot_pose[3]) if len(paint_pivot_pose) >= 4 else pickup_rx,
            pickup_ry,
            align_rz,
        ]

        staged_pose = list(first_pivot_pose)
        _logger.debug(f"staged_pose = {staged_pose}")
        stage_transition_poses: list[list[float]] = []
        if self._pivot_config.motion_plane == "xy_z_rz" and len(staged_pose) >= 6:
            raw_staged_rz = float(staged_pose[5])
            staged_pose[5] = float(align_rz)
            _logger.info(
                "[PICKUP] xy/rz staged orientation restored: raw_rz=%.3f reference_rz=%.3f selected_rz=%.3f",
                raw_staged_rz,
                float(align_rz),
                float(staged_pose[5]),
            )
        elif self._pivot_config.motion_plane == "xz_y_ry" and len(staged_pose) >= 6:
            raw_staged_ry = float(staged_pose[4])
            staged_pose[5] = float(align_rz)
            staged_pose[4] = float(change_plane_pose[4]) if len(change_plane_pose) >= 5 else float(pickup_ry)
            _logger.info(
                "[PICKUP] xz/ry stage axis selection: raw_ry=%.3f reference_ry=%.3f selected_ry=%.3f fixed_rz=%.3f initial_rotation_deferred=true",
                raw_staged_ry,
                float(align_ry),
                float(staged_pose[4]),
                float(align_rz),
            )

            _logger.info(
                "[PICKUP] xz/ry staged pose: first_pivot=%s change_plane=%s staged=%s",
                [round(float(v), 3) for v in first_pivot_pose[:6]],
                [round(float(v), 3) for v in change_plane_pose[:6]],
                [round(float(v), 3) for v in staged_pose[:6]],
            )

        return PickupToPivotPlan(
            pickup_approach_pose=pickup_approach_pose,
            pickup_pose=pickup_pose,
            lift_pose=list(pickup_approach_pose),
            change_plane_pose=change_plane_pose,
            align_pose=align_pose,
            stage_transition_poses=stage_transition_poses,
            staged_pose=staged_pose,
            paint_pivot_pose=list(paint_pivot_pose),
            source_rotation_deg=source_rotation_deg,
            projected_source_path=source_path,
            projected_pivot_path=projected_pivot_path,
            projected_snapshots=projected_snapshots,
            projected_diagnostics=projected_diagnostics,
        )

    @timed_step(_logger, "pickup_phase", label_arg="label")
    def _move_pickup_phase(self, label: str, pose: list[float], velocity: float | None = None, acceleration: float | None = None) -> bool:
        """Execute one pickup-related robot move with the configured pickup tool and user."""
        _logger.info(
            "[PICKUP] %s tool=%d user=%d pose=%s",
            label,
            self._pickup_tool,
            self._pickup_user,
            [round(v, 3) for v in pose],
        )
        ok = self._robot_service.move_ptp(
            position=pose,
            tool=self._pickup_tool,
            user=self._pickup_user,
            velocity=velocity if velocity is not None else PAINT_PROCESS_CONFIG.pickup_default_vel_percent,
            acceleration=acceleration if acceleration is not None else PAINT_PROCESS_CONFIG.pickup_default_acc_percent,
            wait_to_reach=True,
        )
        return ok

    def _pivot_staging_command_pose(self, pose: list[float], reference_pose: list[float]) -> list[float]:
        """Return the robot command pose for moving the held workpiece into XZ/RY pivot contact."""
        if self._pivot_config.motion_plane != "xz_y_ry":
            return list(pose)
        command_pose = list(pose)
        _logger.info(
            "[PICKUP] xz/ry pivot staging command mapped: planned_xz=(%.3f, %.3f) planned_ry=%.3f planned_rz=%.3f reference_xz=(%.3f, %.3f) reference_ry=%.3f command_xz=(%.3f, %.3f) command_ry=%.3f command_rz=%.3f projection_rotation_sign=%.0f",
            float(pose[0]) if len(pose) >= 1 else 0.0,
            float(pose[2]) if len(pose) >= 3 else 0.0,
            float(pose[4]) if len(pose) >= 5 else 0.0,
            float(pose[5]) if len(pose) >= 6 else 0.0,
            float(self._last_pickup_plan.paint_pivot_pose[0]) if self._last_pickup_plan is not None else float(reference_pose[0]) if len(reference_pose) >= 1 else 0.0,
            float(self._last_pickup_plan.paint_pivot_pose[2]) if self._last_pickup_plan is not None else float(reference_pose[2]) if len(reference_pose) >= 3 else 0.0,
            float(reference_pose[4]) if len(reference_pose) >= 5 else 0.0,
            float(command_pose[0]) if len(command_pose) >= 1 else 0.0,
            float(command_pose[2]) if len(command_pose) >= 3 else 0.0,
            float(command_pose[4]),
            float(command_pose[5]),
            float(self._pivot_config.rotation_direction_sign),
        )
        return command_pose

    def _align_preview_path_to_pickup_plan(
        self,
        path: list[list[float]],
        pickup_plan: PickupToPivotPlan | None,
    ) -> list[list[float]]:
        """Apply the same first-rotation alignment used before pivot execution."""
        if not path or pickup_plan is None:
            return [list(pose) for pose in path]
        rotation_index = self._pivot_config.rotation_index
        if len(path[0]) <= rotation_index or len(pickup_plan.staged_pose) <= rotation_index:
            return [list(pose) for pose in path]
        if self._pivot_config.motion_plane == "xy_z_rz":
            staged_rotation = float(pickup_plan.staged_pose[rotation_index])
            raw_start_rotation = float(path[0][rotation_index])
            rotation_shift = axis_equivalent_shift_degrees(staged_rotation, raw_start_rotation)
        elif self._pivot_config.motion_plane == "xz_y_ry":
            staged_rotation = float(pickup_plan.staged_pose[rotation_index])
            raw_start_rotation = float(path[0][rotation_index])
            rotation_shift = staged_rotation - raw_start_rotation
        else:
            rotation_shift = 0.0
        return _shift_path_rotation(path, rotation_index, rotation_shift)

    def _pivot_execution_command_path(
        self,
        path: list[list[float]],
        *,
        pickup_plan: PickupToPivotPlan | None = None,
    ) -> list[list[float]]:
        """Return robot command poses for XZ/RY pivot execution without changing planned geometry."""
        if not path:
            return []
        command_path = [list(pose) for pose in path]
        plan = pickup_plan or self._last_pickup_plan
        if (
            self._pivot_config.motion_plane == "xz_y_ry"
            and plan is not None
            and len(plan.change_plane_pose) >= 5
        ):
            reference_ry = float(plan.change_plane_pose[4])
            _logger.info(
                "[PIVOT_PATH] xz/ry execution command mapped: planned_start_xz=(%.3f, %.3f) planned_start_ry=%.3f planned_start_rz=%.3f command_start_xz=(%.3f, %.3f) command_start_ry=%.3f command_start_rz=%.3f planned_end_xz=(%.3f, %.3f) planned_end_ry=%.3f planned_end_rz=%.3f command_end_xz=(%.3f, %.3f) command_end_ry=%.3f command_end_rz=%.3f reference_xz=(%.3f, %.3f) reference_ry=%.3f projection_rotation_sign=%.0f",
                float(path[0][0]) if len(path[0]) >= 1 else 0.0,
                float(path[0][2]) if len(path[0]) >= 3 else 0.0,
                float(path[0][4]) if len(path[0]) >= 5 else 0.0,
                float(path[0][5]) if len(path[0]) >= 6 else 0.0,
                float(command_path[0][0]) if len(command_path[0]) >= 1 else 0.0,
                float(command_path[0][2]) if len(command_path[0]) >= 3 else 0.0,
                float(command_path[0][4]) if len(command_path[0]) >= 5 else 0.0,
                float(command_path[0][5]) if len(command_path[0]) >= 6 else 0.0,
                float(path[-1][0]) if len(path[-1]) >= 1 else 0.0,
                float(path[-1][2]) if len(path[-1]) >= 3 else 0.0,
                float(path[-1][4]) if len(path[-1]) >= 5 else 0.0,
                float(path[-1][5]) if len(path[-1]) >= 6 else 0.0,
                float(command_path[-1][0]) if len(command_path[-1]) >= 1 else 0.0,
                float(command_path[-1][2]) if len(command_path[-1]) >= 3 else 0.0,
                float(command_path[-1][4]) if len(command_path[-1]) >= 5 else 0.0,
                float(command_path[-1][5]) if len(command_path[-1]) >= 6 else 0.0,
                float(plan.paint_pivot_pose[0]) if len(plan.paint_pivot_pose) >= 1 else 0.0,
                float(plan.paint_pivot_pose[2]) if len(plan.paint_pivot_pose) >= 3 else 0.0,
                reference_ry,
                float(self._pivot_config.rotation_direction_sign),
            )
        return command_path

    @timed_step(_logger, "vacuum_on")
    def _turn_vacuum_on(self) -> tuple[bool, str]:
        """Enable the vacuum pump before pickup if one is configured."""
        if not self._enable_vacuum_pump:
            _logger.info("[PICKUP] Vacuum pump ON skipped: disabled by configuration")
            return True, ""
        if self._vacuum_pump is None:
            _logger.info("[PICKUP] Vacuum pump ON skipped: pump not configured")
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump ON before pickup")
        if self._vacuum_pump.turn_on():
            return True, ""
        return False, "Pickup approach succeeded, but vacuum pump ON failed"

    @timed_step(_logger, "vacuum_off")
    def _turn_vacuum_off(self) -> tuple[bool, str]:
        """Disable the vacuum pump after staging if one is configured."""
        if not self._enable_vacuum_pump:
            _logger.info("[PICKUP] Vacuum pump OFF skipped: disabled by configuration")
            return True, ""
        if self._vacuum_pump is None:
            _logger.info("[PICKUP] Vacuum pump OFF skipped: pump not configured")
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump OFF after staged pivot move")
        if self._vacuum_pump.turn_off():
            return True, ""
        return False, "Pickup succeeded, but vacuum pump OFF failed after pivot stage"

    @timed_step(_logger, "pre_release_dropoff")
    def _run_pre_release_dropoff(self) -> tuple[bool, str]:
        """Return to the saved pickup-align area before releasing the workpiece."""
        started = perf_counter()
        plan = self._last_pickup_plan
        if plan is None:
            _logger.info("[PICKUP] Pre-release dropoff skipped: no pickup plan")
            return True, ""

        move_started = perf_counter()
        if not self._move_pickup_phase(
            "Returning to align pose for release",
            plan.align_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_release_align_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_release_align_acc_percent,
        ):
            _logger.info(
                "[TIMING] pre_release_dropoff success=false stage=align elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(move_started),
                _elapsed_s(started),
            )
            return False, "Pivot paint finished, but return-to-align move failed before release"

        return True, ""

    @timed_step(_logger, "post_execute_return")
    def _run_post_execute_return(self, failure_message: str) -> tuple[bool, str]:
        """Run post-execution return logic after pivot painting finishes."""
        started = perf_counter()
        if self._post_execute_callback is None:
            _logger.info("[EXECUTE] Post-execute return skipped: callback not configured")
            return True, ""
        try:
            return_started = perf_counter()
            moved = bool(self._post_execute_callback())
        except Exception:
            _logger.exception("[EXECUTE] Post-execute callback failed")
            _logger.info(
                "[TIMING] post_execute_return stage=return success=false total_elapsed_s=%.3f",
                _elapsed_s(started),
            )
            return False, failure_message.format(reason="return-to-calibration failed")
        if not moved:
            _logger.info(
                "[TIMING] post_execute_return stage=return success=false return_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(return_started),
                _elapsed_s(started),
            )
            return False, failure_message.format(reason="return-to-calibration failed")
        return True, ""

    @timed_step(_logger, "execute_pivot_paths")
    def _execute_pivot_paths(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str, int]:
        """Execute all projected pivot paint paths in the prepared execution plan."""
        started = perf_counter()
        total_waypoints = 0
        with timed_block(_logger, "pivot_paths_prepare", label="refresh_runtime_config"):
            self._refresh_runtime_config()
        self._last_process_start_rz = None
        self._last_process_end_pose = None
        for job_index, job in enumerate(execution_plan.execution_jobs, start=1):
            job_label = f"job_{job_index}"
            job_started = perf_counter()
            spline = _pivot_source_path(job, self._pivot_config)
            vel = float(job.get("vel", 10.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            pivot_offset_mm = self._resolve_pivot_offset_mm(job, execution_plan)
            if not spline:
                continue

            anchor_xy = _projection_tool_anchor_xy(job, self._pivot_config)
            tcp_to_tool_local_xy = _tcp_to_tool_local_xy(job, self._pivot_config)
            source_rotation_deg = (
                float(self._last_pickup_plan.source_rotation_deg)
                if self._last_pickup_plan is not None else 0.0
            )
            with timed_block(_logger, "pivot_job_prepare", label=f"{job_label}:build_execution_path"):
                if (
                    job_index == 1
                    and self._last_pickup_plan is not None
                    and self._last_pickup_plan.projected_source_path is spline
                    and self._last_pickup_plan.projected_pivot_path
                ):
                    pivot_path = [list(pose) for pose in self._last_pickup_plan.projected_pivot_path]
                    snapshots = self._last_pickup_plan.projected_snapshots
                    diagnostics = (
                        [dict(item) for item in self._last_pickup_plan.projected_diagnostics]
                        if self._last_pickup_plan.projected_diagnostics is not None else None
                    )
                    pivot_pose = list(self._last_pickup_plan.paint_pivot_pose)
                    projected = (pivot_path, snapshots, diagnostics, pivot_pose)
                    _logger.info(
                        "[PIVOT_PATH] Reusing pickup-stage projected path for %s: points=%d source_rotation_deg=%.3f",
                        job_label,
                        len(pivot_path),
                        source_rotation_deg,
                    )
                else:
                    projected = self._build_pivot_execution_path(
                        spline,
                        pivot_offset_mm=pivot_offset_mm,
                        align_start_to_zero_rz=False,
                        anchor_xy=anchor_xy,
                        source_rotation_deg=source_rotation_deg,
                    )
            if not projected:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=build total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    _elapsed_s(job_started),
                )
                return False, "Pickup succeeded, but pivot-path geometry could not be built", total_waypoints
            pivot_path, snapshots, diagnostics, pivot_pose = projected
            if not pivot_path:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=build total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    _elapsed_s(job_started),
                )
                return False, "Pickup succeeded, but pivot-path geometry could not be built", total_waypoints
            if (
                self._pivot_config.motion_plane == "xz_y_ry"
                and self._flip_xz_ry_execution_rotation_direction
                and pivot_path
            ):
                _logger.info(
                    "[PIVOT_PATH] XZ/RY desired rotation direction was applied during projection; command path will not mirror RY afterward"
                )
            rotation_shift = 0.0
            rotation_index = self._pivot_config.rotation_index
            if (
                self._pivot_config.motion_plane == "xy_z_rz"
                and self._last_pickup_plan is not None
                and pivot_path
                and len(pivot_path[0]) > rotation_index
                and len(self._last_pickup_plan.staged_pose) > rotation_index
            ):
                staged_rotation = float(self._last_pickup_plan.staged_pose[rotation_index])
                raw_start_rotation = float(pivot_path[0][rotation_index])
                rotation_shift = axis_equivalent_shift_degrees(staged_rotation, raw_start_rotation)
                if abs(rotation_shift) > 1e-9:
                    with timed_block(_logger, "pivot_job_prepare", label=f"{job_label}:shift_xy_rz_rotation"):
                        pivot_path = _shift_path_rotation(pivot_path, rotation_index, rotation_shift)
                    _logger.info(
                        "[PIVOT_PATH] Applied xy/rz axis-equivalent path shift: staged_rz=%.3f raw_start_rz=%.3f shift=%.3f selected_start_rz=%.3f",
                        staged_rotation,
                        raw_start_rotation,
                        rotation_shift,
                        float(pivot_path[0][rotation_index]),
                    )
            if (
                self._pivot_config.motion_plane == "xz_y_ry"
                and self._last_pickup_plan is not None
                and pivot_path
                and len(pivot_path[0]) > rotation_index
                and len(self._last_pickup_plan.staged_pose) > rotation_index
            ):
                staged_ry = float(self._last_pickup_plan.staged_pose[rotation_index])
                raw_start_ry = float(pivot_path[0][rotation_index])
                rotation_shift = staged_ry - raw_start_ry
                if abs(rotation_shift) > 1e-9:
                    with timed_block(_logger, "pivot_job_prepare", label=f"{job_label}:shift_xz_ry_rotation"):
                        pivot_path = _shift_path_rotation(pivot_path, rotation_index, rotation_shift)
                    _logger.info(
                        "[PIVOT_PATH] Applied xz/ry staging RY alignment shift: staged_ry=%.3f raw_start_ry=%.3f shift=%.3f selected_start_ry=%.3f",
                        staged_ry,
                        raw_start_ry,
                        rotation_shift,
                        float(pivot_path[0][rotation_index]),
                    )

            with timed_block(_logger, "pivot_job_prepare", label=f"{job_label}:build_command_path"):
                command_pivot_path = self._pivot_execution_command_path(pivot_path)
            if self._last_process_start_rz is None and command_pivot_path:
                self._last_process_start_rz = float(command_pivot_path[0][5]) if len(command_pivot_path[0]) >= 6 else 0.0

            first_pose = [round(float(value), 3) for value in command_pivot_path[0][:6]]
            last_pose = [round(float(value), 3) for value in command_pivot_path[-1][:6]]
            staged_delta_mm = 0.0
            if self._last_process_end_pose is None and command_pivot_path:
                staged_delta_mm = float(
                    np.linalg.norm(
                        np.asarray(command_pivot_path[0][:3], dtype=float)
                        - np.asarray(
                            execution_plan.execution_jobs[0].get("execution_path", command_pivot_path)[0][:3],
                            dtype=float,
                        )
                    )
                )
            _logger.info(
                "[PIVOT_PATH] command_truth job=%d first_pose=%s last_pose=%s total_xyz_len_mm=%.3f",
                job_index,
                first_pose,
                last_pose,
                _path_length_mm(command_pivot_path),
            )

            with timed_block(_logger, "pivot_job_debug", label=f"{job_label}:build_diagnostics"):
                if abs(rotation_shift) > 1e-9 and diagnostics is not None:
                    diagnostics = [dict(item) for item in diagnostics]
                    for item in diagnostics:
                        if "current_rz" in item:
                            item["current_rz"] = float(item["current_rz"]) + rotation_shift
                diagnostics = _diagnostics_with_command_rotation(
                    diagnostics,
                    command_pivot_path,
                    rotation_index,
                )
            with timed_block(_logger, "pivot_job_debug", label=f"{job_label}:write_debug_dump"):
                write_pivot_debug_dump(
                    debug_dump_dir=self._debug_dump_dir,
                    pivot_config=self._pivot_config,
                    source_path=spline,
                    pivot_path=command_pivot_path,
                    diagnostics=diagnostics,
                    pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                    anchor_xy=anchor_xy,
                    source_rotation_deg=source_rotation_deg,
                    pattern_type=pattern_type,
                    stage="execute",
                )
            if PAINT_PROCESS_CONFIG.enable_pivot_debug_plot:
                with timed_block(_logger, "pivot_job_debug", label=f"{job_label}:write_debug_plot"):
                    write_pivot_debug_plot(
                        debug_dump_dir=self._debug_dump_dir,
                        pivot_config=self._pivot_config,
                        source_path=spline,
                        pivot_path=command_pivot_path,
                        snapshots=snapshots,
                        diagnostics=diagnostics,
                        pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                        pattern_type=pattern_type,
                        stage="execute",
                        anchor_xy=anchor_xy,
                        source_rotation_deg=source_rotation_deg,
                    )

            with timed_block(_logger, "pivot_job_prepare", label=f"{job_label}:preflight"):
                preflight_ok, preflight_message = self._validate_xz_ry_pivot_path(command_pivot_path)

            if not preflight_ok:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=preflight input_pts=%d output_pts=%d total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(command_pivot_path),
                    _elapsed_s(job_started),
                )
                return False, preflight_message, total_waypoints

            execute_started = perf_counter()
            with timed_block(_logger, "pivot_job_robot_execute", label=f"{job_label}:{pattern_type}"):
                result = self._execute_paint_trajectory_with_optional_trace(
                    command_pivot_path=command_pivot_path,
                    vel=vel,
                    acc=acc,
                    pivot_pose=pivot_pose,
                    pattern_type=pattern_type,
                    stage="execute",
                    tcp_to_tool_local_xy=tcp_to_tool_local_xy,
                )
            if result not in (0, True, None):
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(command_pivot_path),
                    _elapsed_s(execute_started),
                    _elapsed_s(job_started),
                )
                return False, f"Pickup succeeded, but {pattern_type} pivot paint failed with code {result}", total_waypoints
            total_waypoints += len(command_pivot_path)
            self._last_process_end_pose = list(command_pivot_path[-1])
            _logger.info(
                "[TIMING] pivot_job index=%d pattern=%s success=true input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                job_index,
                pattern_type,
                len(spline),
                len(command_pivot_path),
                _elapsed_s(execute_started),
                _elapsed_s(job_started),
            )
        _logger.info(
            "[TIMING] pivot_paths success=true jobs=%d total_waypoints=%d elapsed_s=%.3f",
            len(execution_plan.execution_jobs),
            total_waypoints,
            _elapsed_s(started),
        )
        return True, "", total_waypoints

    @timed_step(_logger, "pickup_to_pivot")
    def _execute_pickup_to_pivot_stage(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run the pickup-only sequence: approach, vacuum on, descend, lift-align, and stage at the pivot."""
        started = perf_counter()
        _logger.info("[TIMING] pickup_to_pivot entered")
        if self._robot_service is None:
            return False, "Robot service is not available"

        plan_started = perf_counter()
        with timed_block(_logger, "pickup_to_pivot_prepare", label="build_pickup_and_stage_poses"):
            plan = self._build_pickup_and_stage_poses(execution_plan)
        if plan is None:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=build_poses total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Could not compute pickup-to-pivot poses"
        self._last_pickup_plan = plan
        _logger.info("[TIMING] pickup_to_pivot stage=build_poses elapsed_s=%.3f", _elapsed_s(plan_started))

        ok, msg = self._turn_vacuum_on()
        if not ok:
            _logger.info("[TIMING] pickup_to_pivot success=false stage=vacuum_on total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        if not self._move_pickup_phase(
            "Moving to pickup approach pose",
            plan.pickup_approach_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_approach_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_approach_acc_percent,
        ):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=approach total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup approach move failed"

        if not self._move_pickup_phase(
            "Descending to pickup pose", plan.pickup_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_descend_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_descend_acc_percent,
        ):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=descend total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup descend move failed"

        if not self._move_pickup_phase(
            "Lifting from pickup pose",
            plan.lift_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_lift_align_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_lift_align_acc_percent,
        ):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=lift total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but lift move failed"

        if not self._move_pickup_phase(
            "Aligning workpiece to paint axis",
            plan.align_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_lift_align_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_lift_align_acc_percent,
        ):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=align total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but align move failed"

        combine_change_plane = PAINT_PROCESS_CONFIG.pickup_combine_change_plane_with_first_contact
        if combine_change_plane:
            with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                _logger.info(
                    "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                )
        elif not self._move_pickup_phase(
            "Changing plane",
            plan.change_plane_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_change_plane_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_change_plane_acc_percent,
        ):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=change_plane total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but change-plane move failed"

        for transition_index, transition_pose in enumerate(plan.stage_transition_poses, start=1):
            if not self._move_pickup_phase(
                f"Stage transition {transition_index}",
                self._pivot_staging_command_pose(transition_pose, plan.change_plane_pose),
                velocity=PAINT_PROCESS_CONFIG.pickup_stage_transition_vel_percent,
                acceleration=PAINT_PROCESS_CONFIG.pickup_stage_transition_acc_percent,
            ):
                _logger.info(
                    "[TIMING] pickup_to_pivot success=false stage=stage_transition_%d total_elapsed_s=%.3f",
                    transition_index,
                    _elapsed_s(started),
                )
                return False, f"Pickup succeeded, but stage transition {transition_index} failed"

        staged_command_pose = self._pivot_staging_command_pose(plan.staged_pose, plan.change_plane_pose)
        staging_offset_pose = _paint_axis_staging_offset_pose(staged_command_pose, self._pivot_config)
        _logger.info(
            "[PICKUP] staging offset before pivot contact: z_offset_mm=%.3f paint_axis=%s paint_axis_offset_mm=%.3f direction=%s contact_pose=%s offset_pose=%s",
            _STAGING_Z_OFFSET_MM,
            self._pivot_config.translation_axis,
            _STAGING_PAINT_AXIS_OFFSET_MM,
            self._pivot_config.translation_direction,
            [round(float(v), 3) for v in staged_command_pose[:6]],
            [round(float(v), 3) for v in staging_offset_pose[:6]],
        )
        if not self._move_pickup_phase(
            "Moving to staging offset before first pivot contact pose",
            staging_offset_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_first_contact_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_first_contact_acc_percent,
        ):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=staged_pose total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but move to staging offset failed"
        return True, "Pickup completed and robot is positioned before the first pivot contact pose"

    def execute_pickup_and_paint(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run pickup, staging, projected pivot paint execution, and post-run return."""
        with timing_session("pickup_and_paint") as recorder:
            started = perf_counter()
            total_waypoints = 0
            result: tuple[bool, str]

            ok, msg = self._execute_pickup_to_pivot_stage(execution_plan)
            if not ok:
                _logger.info("[TIMING] pickup_and_paint success=false stage=pickup total_elapsed_s=%.3f", _elapsed_s(started))
                result = (False, msg)
            else:
                result, total_waypoints = self._execute_pivot_paint_and_release(execution_plan, started)
                result = self._run_post_execute_return_after_pickup(result, started)

            recorder.record(
                step="pickup_and_paint",
                label="",
                success=result[0],
                elapsed_s=_elapsed_s(started),
                started_at=started,
                ended_at=perf_counter(),
            )
            self._write_timing_summary(recorder)
            return result

    @timed_step(_logger, "pivot_paint_and_release")
    def _execute_pivot_paint_and_release(
        self,
        execution_plan: WorkpieceExecutionPlan,
        started: float,
    ) -> tuple[tuple[bool, str], int]:
        ok, msg, total_waypoints = self._execute_pivot_paths(execution_plan)
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pivot total_elapsed_s=%.3f", _elapsed_s(started))
            return (False, msg), total_waypoints

        ok, msg = self._run_pre_release_dropoff()
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pre_release_dropoff total_elapsed_s=%.3f", _elapsed_s(started))
            return (False, msg), total_waypoints

        ok, msg = self._turn_vacuum_off()
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=vacuum_off total_elapsed_s=%.3f", _elapsed_s(started))
            return (False, msg), total_waypoints

        _logger.info("[EXECUTE] Pickup and pivot paint completed: jobs=%d total_waypoints=%d", len(execution_plan.execution_jobs), total_waypoints)
        return (True, (
            f"Pickup, alignment, and pivot paint completed "
            f"for {len(execution_plan.execution_jobs)} path(s), {total_waypoints} waypoints"
        )), total_waypoints

    @timed_step(_logger, "return_after_pickup")
    def _run_post_execute_return_after_pickup(
        self,
        result: tuple[bool, str],
        started: float,
    ) -> tuple[bool, str]:
        ok, msg = self._run_post_execute_return(
            "Pickup and pivot paint finished, but {reason}"
        )
        if ok:
            return result

        _logger.info("[TIMING] pickup_and_paint success=false stage=post_return total_elapsed_s=%.3f", _elapsed_s(started))
        if result[0]:
            return False, msg
        return False, f"{result[1]}; additionally, return-to-calibration failed"

    def _write_timing_summary(self, recorder: TimingRecorder) -> None:
        try:
            csv_path = recorder.write_csv(self._debug_dump_dir)
            recorder.log_summary(_logger, csv_path=csv_path)
        except Exception:
            _logger.exception("[TIMING_SUMMARY] Failed to write paint timing summary")
