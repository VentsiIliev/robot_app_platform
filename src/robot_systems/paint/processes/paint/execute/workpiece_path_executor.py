from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Optional

import numpy as np

from src.engine.geometry.planar import rotate_xy, unwrap_degrees
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
    write_pivot_debug_dump,
    write_pivot_debug_plot,
)
from src.robot_systems.paint.processes.paint.execute.pivot_projection import (
    project_paint_motion_geometry,
    rebase_projected_paint_path_to_zero_start_rz,
)

_logger = logging.getLogger(__name__)


def _elapsed_s(start: float) -> float:
    return perf_counter() - float(start)


def _blend_pose(start_pose: list[float], end_pose: list[float], ratio: float) -> list[float]:
    """Linearly interpolate a 6D pose, unwrapping orientation against the start pose."""
    ratio = max(0.0, min(1.0, float(ratio)))
    pose: list[float] = []
    for index in range(6):
        start_value = float(start_pose[index])
        end_value = float(end_pose[index])
        if index >= 3:
            end_value = float(np.unwrap(np.radians([start_value, end_value]))[-1] * 180.0 / np.pi)
        pose.append(start_value + (end_value - start_value) * ratio)
    return pose


def _path_length_mm(path: list[list[float]]) -> float:
    """Return the cumulative Cartesian XYZ path length."""
    if len(path) < 2:
        return 0.0
    total = 0.0
    for start_pose, end_pose in zip(path, path[1:]):
        total += float(np.linalg.norm(np.asarray(end_pose[:3], dtype=float) - np.asarray(start_pose[:3], dtype=float)))
    return total

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

def _normalize_pivot_config(
    *,
    motion_plane: str = "xy_z_rz",
    translation_axis: str = "x",
    pivot_side: str = "negative",
    translation_direction: str = "forward",
    apply_camera_to_tcp_for_pickup: bool = False,
    camera_to_tcp_x_offset: float = 0.0,
    camera_to_tcp_y_offset: float = 0.0,
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
    )


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

    def prepare_workpiece_preview(self, workpiece: dict) -> WorkpieceExecutionPlan:
        """Build and cache the execution plan for a paint workpiece."""
        if self._path_preparation_service is None:
            raise RuntimeError("Path preparation service is not available")
        self._last_execution_plan = self._path_preparation_service.build_execution_plan(workpiece)
        return self._last_execution_plan

    def get_last_execution_plan(self) -> WorkpieceExecutionPlan | None:
        """Return the last paint preview plan prepared by this executor."""
        return self._last_execution_plan

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

    def supports_pickup_to_pivot(self) -> bool:
        """Report that this executor supports pickup and staging before paint execution."""
        return True

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
        base_pivot_pose = self._resolve_base_position()
        if base_pivot_pose is None or len(base_pivot_pose) < 3:
            return [], base_pivot_pose
        paths = []
        last_pivot_pose = list(base_pivot_pose)
        for job in execution_plan.execution_jobs:
            source_path = job.get("execution_path") or job.get("path") or []
            if not source_path:
                continue
            pivot_pose = self._apply_pivot_offset(
                base_pivot_pose,
                self._resolve_pivot_offset_mm(job, execution_plan),
            )
            if pivot_pose is None or len(pivot_pose) < 3:
                continue
            last_pivot_pose = list(pivot_pose)
            center_path, _, diagnostics = project_paint_motion_geometry(
                source_path,
                pivot_pose,
                self._pivot_config,
            )
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
        base_pivot_pose = self._resolve_base_position()
        if base_pivot_pose is None or len(base_pivot_pose) < 3:
            return [], base_pivot_pose
        motion = []
        last_pivot_pose = list(base_pivot_pose)
        for job in execution_plan.execution_jobs:
            source_path = job.get("execution_path") or job.get("path") or []
            if not source_path:
                continue
            pivot_pose = self._apply_pivot_offset(
                base_pivot_pose,
                self._resolve_pivot_offset_mm(job, execution_plan),
            )
            if pivot_pose is None or len(pivot_pose) < 3:
                continue
            last_pivot_pose = list(pivot_pose)
            _, snapshots, _ = project_paint_motion_geometry(
                source_path,
                pivot_pose,
                self._pivot_config,
            )
            motion.append(snapshots)
        return motion, last_pivot_pose


    def _build_pivot_execution_path(
        self,
        spline: list[list[float]],
        *,
        pivot_offset_mm: float = 0.0,
        align_start_to_zero_rz: bool = False,
    ) -> list[list[float]] | None:
        """Project one prepared spline into the real pivot execution trajectory."""
        started = perf_counter()
        pivot_pose = self._apply_pivot_offset(self._resolve_base_position(), pivot_offset_mm)
        if pivot_pose is None or len(pivot_pose) < 3:
            _logger.info("[TIMING] pivot_path_build status=missing_pivot elapsed_s=%.3f", _elapsed_s(started))
            return None
        pivot_path, _, _ = project_paint_motion_geometry(
            spline,
            pivot_pose,
            self._pivot_config,
        )
        _logger.debug("Simulated pivot path has %d points", len(pivot_path))
        if align_start_to_zero_rz:
            pivot_path = rebase_projected_paint_path_to_zero_start_rz(
                pivot_path,
                self._pivot_config,
            )
        _logger.info(
            "[TIMING] pivot_path_build input_pts=%d output_pts=%d zero_start_rz=%s elapsed_s=%.3f",
            len(spline),
            len(pivot_path) if pivot_path else 0,
            bool(align_start_to_zero_rz),
            _elapsed_s(started),
        )
        return pivot_path

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
            spline = job.get("execution_path") or job.get("path") or []
            _logger.debug(f"Execution path before build_pivot_execution_path: {len(spline)}")
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            pivot_offset_mm = self._resolve_pivot_offset_mm(job, execution_plan)

            if not spline:
                continue

            pivot_pose = self._apply_pivot_offset(self._resolve_base_position(), pivot_offset_mm)
            if pivot_pose is None or len(pivot_pose) < 3:
                return False, "Pivot-path execution requires a valid base/pivot position"
            pivot_path, _, diagnostics = project_paint_motion_geometry(
                spline,
                pivot_pose,
                self._pivot_config,
            )
            if not pivot_path:
                return False, "Pivot-path execution requires a valid base/pivot position"
            _logger.debug(f"Pivot path after build_pivot_execution_path: {len(pivot_path)}")

            # self._write_pivot_debug_dump(
            #     source_path=spline,
            #     pivot_path=pivot_path,
            #     diagnostics=diagnostics,
            #     pivot_pose=pivot_pose,
            #     pattern_type=pattern_type,
            #     stage="execute",
            # )
            result = self._robot_service.execute_trajectory(
                pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
            if result not in (0, True, None):
                return False, f"{pattern_type} pivot-path execution failed with code {result}"
            total_waypoints += len(spline)
            _logger.info(
                "[EXECUTE] [RUN PROCESS] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
                len(spline), mode, vel, acc,
            )

        if self._post_execute_callback is not None:
            if not self._robot_service.unwind_joint6(
                blocking=True,
                queue_if_busy=True,
                vel=100.0,
                acc=100.0,
            ):
                return False, "Execution finished, but explicit unwind failed"
            _logger.info("[EXECUTE] Explicit Joint_6 unwind completed")
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
        self._refresh_runtime_config()
        if not jobs:
            return None

        pickup_pivot_pose = self._resolve_pickup_base_position()
        paint_pivot_pose = self._resolve_base_position()
        if pickup_pivot_pose is None or len(pickup_pivot_pose) < 3:
            return None
        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        source_path = jobs[0].get("execution_path") or jobs[0].get("path") or []
        if not source_path:
            return None

        pivot_offset_mm = self._resolve_pivot_offset_mm(jobs[0], execution_plan)
        paint_pivot_pose = self._apply_pivot_offset(paint_pivot_pose, pivot_offset_mm)
        if paint_pivot_pose is None or len(paint_pivot_pose) < 3:
            return None

        projected_pivot_path, _, _ = project_paint_motion_geometry(
            source_path,
            paint_pivot_pose,
            self._pivot_config,
        )
        if not projected_pivot_path:
            return None

        first_pivot_pose = list(projected_pivot_path[0])
        pickup_target_point_name = str(
            jobs[0].get("pickup_target_point_name", "") or ""
        ).strip().lower()
        workpiece_height_mm = float(jobs[0].get("workpiece_height_mm", 0.0) or 0.0)
        pickup_xy = jobs[0].get("pickup_xy")
        pickup_centroid_x = float(pickup_xy[0])
        pickup_centroid_y = float(pickup_xy[1])
        pickup_rx = float(pickup_pivot_pose[3]) if len(pickup_pivot_pose) >= 4 else 180.0
        pickup_ry = float(pickup_pivot_pose[4]) if len(pickup_pivot_pose) >= 5 else 0.0

        pickup_z = self._pickup_z_mm
        if pickup_z is None:
            pickup_z = self._pickup_safety_z_min_mm + workpiece_height_mm + PAINT_PROCESS_CONFIG.pickup_contact_offset_mm

        pickup_rz = float(jobs[0].get("pickup_rz", 0.0))
        should_apply_tcp_offset = False
        pickup_tcp_dx, pickup_tcp_dy = 0.0, 0.0
        _logger.info(
            "[PICKUP] pickup_xy=(%.3f, %.3f) pickup_rz=%.3f pickup_target=%s workpiece_height=%.3f pickup_z=%.3f safety_z_min=%.3f apply_tcp_offset=%s configured_tcp_offset=(%.3f, %.3f) rotated_tcp_offset=(%.3f, %.3f)",
            pickup_centroid_x,
            pickup_centroid_y,
            pickup_rz,
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
        align_rz = self._pivot_strategy.compute_pickup_align_rotation(
            pickup_rz=pickup_rz,
            pickup_ry=pickup_ry,
            first_pivot_pose=first_pivot_pose,
            paint_pivot_pose=paint_pivot_pose,
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
        stage_transition_poses: list[list[float]] = []
        return PickupToPivotPlan(
            pickup_approach_pose=pickup_approach_pose,
            pickup_pose=pickup_pose,
            lift_pose=list(pickup_approach_pose),
            change_plane_pose=change_plane_pose,
            align_pose=align_pose,
            stage_transition_poses=stage_transition_poses,
            staged_pose=staged_pose,
        )

    def _move_pickup_phase(self, label: str, pose: list[float]) -> bool:
        """Execute one pickup-related robot move with the configured pickup tool and user."""
        started = perf_counter()
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
            velocity=PAINT_PROCESS_CONFIG.pickup_default_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_default_acc_percent,
            wait_to_reach=True,
        )
        _logger.info("[TIMING] pickup_phase label=%s success=%s elapsed_s=%.3f", label, bool(ok), _elapsed_s(started))
        return ok

    def _turn_vacuum_on(self) -> tuple[bool, str]:
        """Enable the vacuum pump before pickup if one is configured."""
        started = perf_counter()
        if not self._enable_vacuum_pump:
            _logger.info("[TIMING] vacuum_on skipped=true reason=disabled_by_configuration elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        if self._vacuum_pump is None:
            _logger.info("[TIMING] vacuum_on skipped=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump ON before pickup")
        if self._vacuum_pump.turn_on():
            _logger.info("[TIMING] vacuum_on success=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[TIMING] vacuum_on success=false elapsed_s=%.3f", _elapsed_s(started))
        return False, "Pickup approach succeeded, but vacuum pump ON failed"

    def _turn_vacuum_off(self) -> tuple[bool, str]:
        """Disable the vacuum pump after staging if one is configured."""
        started = perf_counter()
        if not self._enable_vacuum_pump:
            _logger.info("[TIMING] vacuum_off skipped=true reason=disabled_by_configuration elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        if self._vacuum_pump is None:
            _logger.info("[TIMING] vacuum_off skipped=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[PICKUP] Turning vacuum pump OFF after staged pivot move")
        if self._vacuum_pump.turn_off():
            _logger.info("[TIMING] vacuum_off success=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        _logger.info("[TIMING] vacuum_off success=false elapsed_s=%.3f", _elapsed_s(started))
        return False, "Pickup succeeded, but vacuum pump OFF failed after pivot stage"

    def _run_pre_release_dropoff(self) -> tuple[bool, str]:
        """Return to the saved pickup-align area before releasing the workpiece."""
        started = perf_counter()
        plan = self._last_pickup_plan
        if plan is None:
            _logger.info("[TIMING] pre_release_dropoff skipped=true reason=no_pickup_plan elapsed_s=%.3f", _elapsed_s(started))
            return True, ""

        move_started = perf_counter()
        if not self._move_pickup_phase("Returning to align pose for release", plan.align_pose):
            _logger.info(
                "[TIMING] pre_release_dropoff success=false stage=align elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(move_started),
                _elapsed_s(started),
            )
            return False, "Pivot paint finished, but return-to-align move failed before release"

        rotate_started = perf_counter()
        if not self._move_pickup_phase("Changing back to original pickup orientation", plan.pickup_approach_pose):
            _logger.info(
                "[TIMING] pre_release_dropoff success=false stage=restore_orientation move_elapsed_s=%.3f rotate_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(move_started),
                _elapsed_s(rotate_started),
                _elapsed_s(started),
            )
            return False, "Pivot paint finished, but original-orientation restore failed before release"

        _logger.info(
            "[TIMING] pre_release_dropoff success=true align_elapsed_s=%.3f restore_elapsed_s=%.3f total_elapsed_s=%.3f",
            _elapsed_s(move_started),
            _elapsed_s(rotate_started),
            _elapsed_s(started),
        )
        return True, ""

    def _run_post_execute_return(self, failure_message: str) -> tuple[bool, str]:
        """Run unwind and post-execution return logic after pivot painting finishes."""
        started = perf_counter()
        if self._post_execute_callback is None:
            _logger.info("[TIMING] post_execute_return skipped=true elapsed_s=%.3f", _elapsed_s(started))
            return True, ""
        unwind_started = perf_counter()
        if not self._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=True,
            vel=100.0,
            acc=100.0,
        ):
            _logger.info("[TIMING] post_execute_return stage=unwind success=false total_elapsed_s=%.3f", _elapsed_s(started))
            return False, failure_message.format(reason="explicit unwind failed")
        try:
            return_started = perf_counter()
            moved = bool(self._post_execute_callback())
        except Exception:
            _logger.exception("[EXECUTE] Post-execute callback failed")
            _logger.info(
                "[TIMING] post_execute_return stage=return success=false unwind_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(unwind_started),
                _elapsed_s(started),
            )
            return False, failure_message.format(reason="return-to-calibration failed")
        if not moved:
            _logger.info(
                "[TIMING] post_execute_return stage=return success=false unwind_elapsed_s=%.3f return_elapsed_s=%.3f total_elapsed_s=%.3f",
                _elapsed_s(unwind_started),
                _elapsed_s(return_started),
                _elapsed_s(started),
            )
            return False, failure_message.format(reason="return-to-calibration failed")
        _logger.info(
            "[TIMING] post_execute_return success=true unwind_elapsed_s=%.3f return_elapsed_s=%.3f total_elapsed_s=%.3f",
            _elapsed_s(unwind_started),
            _elapsed_s(return_started),
            _elapsed_s(started),
        )
        return True, ""

    def _execute_pivot_paths(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str, int]:
        """Execute all projected pivot paint paths in the prepared execution plan."""
        started = perf_counter()
        total_waypoints = 0
        self._refresh_runtime_config()
        self._last_process_start_rz = None
        self._last_process_end_pose = None
        for job_index, job in enumerate(execution_plan.execution_jobs, start=1):
            job_started = perf_counter()
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 10.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            pivot_offset_mm = self._resolve_pivot_offset_mm(job, execution_plan)
            if not spline:
                continue

            pivot_path = self._build_pivot_execution_path(
                spline,
                pivot_offset_mm=pivot_offset_mm,
                align_start_to_zero_rz=False,
            )
            if not pivot_path:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=build total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    _elapsed_s(job_started),
                )
                return False, "Pickup succeeded, but pivot-path geometry could not be built", total_waypoints
            if self._flip_xz_ry_execution_rotation_direction and pivot_path:
                reference_ry = float(pivot_path[0][4]) if len(pivot_path[0]) >= 5 else 0.0
                pivot_path = self._pivot_strategy.maybe_flip_execution_rotation_direction(
                    pivot_path=pivot_path,
                    enabled=True,
                )
                if self._pivot_strategy.requires_reachability_preflight:
                    _logger.info(
                        "[PIVOT_PATH] Flipped xz/ry execution rotation direction around start RY=%.3f",
                        reference_ry,
                    )
            if self._last_process_start_rz is None and pivot_path:
                self._last_process_start_rz = float(pivot_path[0][5]) if len(pivot_path[0]) >= 6 else 0.0

            first_pose = [round(float(value), 3) for value in pivot_path[0][:6]]
            last_pose = [round(float(value), 3) for value in pivot_path[-1][:6]]
            staged_delta_mm = 0.0
            if self._last_process_end_pose is None and pivot_path:
                staged_delta_mm = float(
                    np.linalg.norm(
                        np.asarray(pivot_path[0][:3], dtype=float)
                        - np.asarray(execution_plan.execution_jobs[0].get("execution_path", pivot_path)[0][:3], dtype=float)
                    )
                )
            _logger.info(
                "[PIVOT_PATH] job=%d first_pose=%s last_pose=%s total_xyz_len_mm=%.3f",
                job_index,
                first_pose,
                last_pose,
                _path_length_mm(pivot_path),
            )

            pivot_pose = self._apply_pivot_offset(self._resolve_base_position(), pivot_offset_mm)
            if pivot_pose is not None and len(pivot_pose) >= 3:
                _, snapshots, diagnostics = project_paint_motion_geometry(
                    spline,
                    pivot_pose,
                    self._pivot_config,
                )
            else:
                snapshots = None
                diagnostics = None
            write_pivot_debug_dump(
                debug_dump_dir=self._debug_dump_dir,
                pivot_config=self._pivot_config,
                source_path=spline,
                pivot_path=pivot_path,
                diagnostics=diagnostics,
                pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                pattern_type=pattern_type,
                stage="execute",
            )
            write_pivot_debug_plot(
                debug_dump_dir=self._debug_dump_dir,
                pivot_config=self._pivot_config,
                source_path=spline,
                pivot_path=pivot_path,
                snapshots=snapshots,
                diagnostics=diagnostics,
                pivot_pose=list(pivot_pose) if pivot_pose is not None else None,
                pattern_type=pattern_type,
                stage="execute",
            )

            preflight_ok, preflight_message = self._validate_xz_ry_pivot_path(pivot_path)
            if not preflight_ok:
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false stage=preflight input_pts=%d output_pts=%d total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(pivot_path),
                    _elapsed_s(job_started),
                )
                return False, preflight_message, total_waypoints

            execute_started = perf_counter()
            result = self._robot_service.execute_trajectory(
                pivot_path,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode="per_waypoint",
            )
            if result not in (0, True, None):
                _logger.info(
                    "[TIMING] pivot_job index=%d pattern=%s success=false input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                    job_index,
                    pattern_type,
                    len(spline),
                    len(pivot_path),
                    _elapsed_s(execute_started),
                    _elapsed_s(job_started),
                )
                return False, f"Pickup succeeded, but {pattern_type} pivot paint failed with code {result}", total_waypoints
            total_waypoints += len(spline)
            self._last_process_end_pose = list(pivot_path[-1])
            _logger.info(
                "[TIMING] pivot_job index=%d pattern=%s success=true input_pts=%d output_pts=%d execute_elapsed_s=%.3f total_elapsed_s=%.3f",
                job_index,
                pattern_type,
                len(spline),
                len(pivot_path),
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

    def execute_pickup_to_pivot(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run the pickup-only sequence: approach, vacuum on, descend, lift, and stage at the pivot."""
        started = perf_counter()
        if self._robot_service is None:
            return False, "Robot service is not available"

        plan_started = perf_counter()
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

        if not self._move_pickup_phase("Moving to pickup approach pose", plan.pickup_approach_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=approach total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup approach move failed"

        if not self._move_pickup_phase("Descending to pickup pose", plan.pickup_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=descend total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup descend move failed"

        if not self._move_pickup_phase("Lifting from pickup pose", plan.lift_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=lift total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but lift move failed"

        if not self._move_pickup_phase("Aligning rotation at pickup pose", plan.align_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=align total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but align move failed"

        if not self._move_pickup_phase("Changing plane", plan.change_plane_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=change_plane total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but change-plane move failed"

        for transition_index, transition_pose in enumerate(plan.stage_transition_poses, start=1):
            if not self._move_pickup_phase(
                f"Stage transition {transition_index}",
                transition_pose,
            ):
                _logger.info(
                    "[TIMING] pickup_to_pivot success=false stage=stage_transition_%d total_elapsed_s=%.3f",
                    transition_index,
                    _elapsed_s(started),
                )
                return False, f"Pickup succeeded, but stage transition {transition_index} failed"

        if not self._move_pickup_phase("Moving to first pivot contact pose", plan.staged_pose):
            _logger.info("[TIMING] pickup_to_pivot success=false stage=staged_pose total_elapsed_s=%.3f", _elapsed_s(started))
            return False, "Pickup succeeded, but move to first pivot contact pose failed"
        _logger.info("[TIMING] pickup_to_pivot success=true total_elapsed_s=%.3f", _elapsed_s(started))
        return True, "Pickup completed and robot is positioned at the first pivot contact pose"

    def execute_pickup_and_paint(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run pickup, staging, projected pivot paint execution, and post-run return."""
        started = perf_counter()
        ok, msg = self.execute_pickup_to_pivot(execution_plan)
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pickup total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg, total_waypoints = self._execute_pivot_paths(execution_plan)
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pivot total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg = self._run_pre_release_dropoff()
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=pre_release_dropoff total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg = self._turn_vacuum_off()
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=vacuum_off total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        ok, msg = self._run_post_execute_return(
            "Pickup and pivot paint finished, but {reason}"
        )
        if not ok:
            _logger.info("[TIMING] pickup_and_paint success=false stage=post_return total_elapsed_s=%.3f", _elapsed_s(started))
            return False, msg

        _logger.info(
            "[TIMING] pickup_and_paint success=true jobs=%d total_waypoints=%d total_elapsed_s=%.3f",
            len(execution_plan.execution_jobs),
            total_waypoints,
            _elapsed_s(started),
        )
        return True, (
            f"Pickup, alignment, and pivot paint completed "
            f"for {len(execution_plan.execution_jobs)} path(s), {total_waypoints} waypoints"
        )
