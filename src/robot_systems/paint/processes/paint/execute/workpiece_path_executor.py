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
)
from src.engine.robot.motion_sequence import MotionSequenceSegment
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
from src.robot_systems.paint.processes.paint.plan import (
    build_paint_contact_source_plan,
    PaintPickupTransferPlanner,
    PickupTransferPlan,
)
from src.robot_systems.paint.processes.paint.execute.dropoff_executor import PaintDropoffExecutor
from src.robot_systems.paint.processes.paint.execute.edge_cleanup_executor import PaintEdgeCleanupExecutor
from src.robot_systems.paint.processes.paint.execute.execution_plane import (
    get_execution_plane_strategy,
)
from src.robot_systems.paint.processes.paint.execute.paint_contact_executor import PaintContactExecutor
from src.robot_systems.paint.processes.paint.execute.pickup_executor import PaintPickupExecutor
from src.robot_systems.paint.processes.paint.execute.diagnostics import (
    elapsed_s,

)
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion import (
    project_paint_contact_motion_continuous,
    rebase_contact_motion_path_to_zero_start_rotation,
)
from src.robot_systems.paint.processes.paint.execute.projection_preview import (
    project_pivot_motion_snapshots_for_editor,
    project_pivot_paths_for_editor,
)
from src.robot_systems.paint.timing import timed_block, timed_step, timing_session

_logger = logging.getLogger(__name__)

_STAGING_Z_OFFSET_MM = -10.0
_STAGING_PAINT_AXIS_OFFSET_MM = 10.0


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
    """Apply a constant shift to one rotation component across a projected path.

    Example:
        _shift_path_rotation(
            [[0, 0, 0, 180, 0, -160], [1, 0, 0, 180, 0, -120]],
            rotation_index=5,
            shift_degrees=180,
        )
        -> [[0, 0, 0, 180, 0, 20], [1, 0, 0, 180, 0, 60]]
    """
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


@dataclass(frozen=True)
class PaintExecutorDependencies:
    """Runtime services and callbacks needed by the paint process executor."""

    robot_service: object
    path_preparation_service: Optional[IWorkpiecePathPreparationService] = None
    base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None
    pickup_base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None
    post_execute_callback: Optional[Callable[[], bool]] = None
    robot_config_provider: Optional[Callable[[], object]] = None
    vacuum_pump: object | None = None

@dataclass(frozen=True)
class PaintExecutorMotionConfig:
    """Robot tool/user and process-motion switches for paint execution."""

    enable_vacuum_pump: bool = True
    pickup_tool: int = 0
    pickup_user: int = 0
    pickup_z_mm: float | None = None
    debug_dump_dir: str | None = None

@dataclass(frozen=True)
class PaintExecutorContactMotionConfig:
    """Configured pivot plane/profile used by paint projection and pickup handoff."""

    motion_plane: str = "xy_z_rz"
    translation_axis: str = "x"
    paint_side: str = "negative"
    translation_direction: str = "forward"
    flip_xz_ry_execution_rotation_direction: bool = False
    mirror_xz_ry_pickup_handoff: bool = False
    apply_camera_to_tcp_for_pickup: bool = False
    camera_to_tcp_x_offset: float = 0.0
    camera_to_tcp_y_offset: float = 0.0

PaintExecutorPivotConfig = PaintExecutorContactMotionConfig


def _normalize_contact_motion_config(
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
        robot_service=None,
        *,
        dependencies: PaintExecutorDependencies | None = None,
        motion_config: PaintExecutorMotionConfig | None = None,
        contact_motion_config: PaintExecutorContactMotionConfig | None = None,
        pivot_config: PaintExecutorContactMotionConfig | None = None,
        **legacy_options,
    ) -> None:
        """Store robot dependencies and initialize the pivot/pickup execution configuration."""
        dependencies = dependencies or PaintExecutorDependencies(
            robot_service=robot_service,
            path_preparation_service=legacy_options.get("path_preparation_service"),
            base_position_provider=legacy_options.get("base_position_provider"),
            pickup_base_position_provider=legacy_options.get("pickup_base_position_provider"),
            post_execute_callback=legacy_options.get("post_execute_callback"),
            robot_config_provider=legacy_options.get("robot_config_provider"),
            vacuum_pump=legacy_options.get("vacuum_pump"),
        )
        motion_config = motion_config or PaintExecutorMotionConfig(
            enable_vacuum_pump=legacy_options.get("enable_vacuum_pump", True),
            pickup_tool=legacy_options.get("pickup_tool", 0),
            pickup_user=legacy_options.get("pickup_user", 0),
            pickup_z_mm=legacy_options.get("pickup_z_mm"),
            debug_dump_dir=legacy_options.get("debug_dump_dir"),
        )
        contact_motion_config = contact_motion_config or pivot_config or PaintExecutorContactMotionConfig(
            motion_plane=legacy_options.get("pivot_motion_plane", "xy_z_rz"),
            translation_axis=legacy_options.get("pivot_translation_axis", "x"),
            paint_side=legacy_options.get("pivot_side", "negative"),
            translation_direction=legacy_options.get("pivot_translation_direction", "forward"),
            flip_xz_ry_execution_rotation_direction=legacy_options.get(
                "flip_xz_ry_execution_rotation_direction",
                False,
            ),
            mirror_xz_ry_pickup_handoff=legacy_options.get("mirror_xz_ry_pickup_handoff", False),
            apply_camera_to_tcp_for_pickup=legacy_options.get("apply_camera_to_tcp_for_pickup", False),
            camera_to_tcp_x_offset=legacy_options.get("camera_to_tcp_x_offset", 0.0),
            camera_to_tcp_y_offset=legacy_options.get("camera_to_tcp_y_offset", 0.0),
        )

        # Dependencies.
        self._robot_service = dependencies.robot_service
        self._path_preparation_service = dependencies.path_preparation_service
        self._base_position_provider = dependencies.base_position_provider
        self._pickup_base_position_provider = dependencies.pickup_base_position_provider or dependencies.base_position_provider
        self._post_execute_callback = dependencies.post_execute_callback
        self._robot_config_provider = dependencies.robot_config_provider
        self._vacuum_pump = dependencies.vacuum_pump

        # Motion settings.
        self._enable_vacuum_pump = bool(motion_config.enable_vacuum_pump)
        self._pickup_tool = int(motion_config.pickup_tool)
        self._pickup_user = int(motion_config.pickup_user)
        self._pickup_z_mm = None if motion_config.pickup_z_mm is None else float(motion_config.pickup_z_mm)
        self._pickup_safety_z_min_mm = 100.0
        self._debug_dump_dir = motion_config.debug_dump_dir

        # Paint contact-motion settings.
        self._configured_contact_motion_plane = str(contact_motion_config.motion_plane or "xy_z_rz").strip().lower()
        self._configured_contact_translation_axis = str(contact_motion_config.translation_axis or "x").strip().lower()
        self._configured_contact_side = str(contact_motion_config.paint_side or "negative").strip().lower()
        self._configured_contact_translation_direction = str(contact_motion_config.translation_direction or "forward").strip().lower()
        self._apply_camera_to_tcp_for_pickup = bool(contact_motion_config.apply_camera_to_tcp_for_pickup)
        self._flip_xz_ry_execution_rotation_direction = bool(contact_motion_config.flip_xz_ry_execution_rotation_direction)
        self._mirror_xz_ry_pickup_handoff = bool(contact_motion_config.mirror_xz_ry_pickup_handoff)
        self._contact_motion_config = _normalize_contact_motion_config(
            motion_plane=contact_motion_config.motion_plane,
            translation_axis=contact_motion_config.translation_axis,
            pivot_side=contact_motion_config.paint_side,
            translation_direction=contact_motion_config.translation_direction,
            apply_camera_to_tcp_for_pickup=contact_motion_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=contact_motion_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=contact_motion_config.camera_to_tcp_y_offset,
            rotation_direction_sign=_xz_ry_projection_rotation_sign(
                contact_motion_config.motion_plane,
                self._flip_xz_ry_execution_rotation_direction,
            ),
        )
        self._pickup_contact_motion_config = _normalize_contact_motion_config(
            motion_plane="xy_z_rz",
            translation_axis=contact_motion_config.translation_axis,
            pivot_side=contact_motion_config.paint_side,
            translation_direction=contact_motion_config.translation_direction,
            apply_camera_to_tcp_for_pickup=contact_motion_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=contact_motion_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=contact_motion_config.camera_to_tcp_y_offset,
        )
        self._contact_motion_strategy = get_execution_plane_strategy(self._contact_motion_config.motion_plane)

        # Per-run state and phase executors.
        self._last_execution_plan: WorkpieceExecutionPlan | None = None
        self._last_pickup_plan: PickupTransferPlan | None = None
        self._pending_stage_pose: list[float] | None = None
        self._dropoff = PaintDropoffExecutor(self)
        self._edge_cleanup = PaintEdgeCleanupExecutor(self)
        self._pickup = PaintPickupExecutor(self)
        self._paint_contact = PaintContactExecutor(self)
        self._pickup_transfer_planner = PaintPickupTransferPlanner(self)
        self._staging_z_offset_mm = _STAGING_Z_OFFSET_MM
        self._staging_paint_axis_offset_mm = _STAGING_PAINT_AXIS_OFFSET_MM
        self._active_contact_base_z_offset_mm: float = 0.0
        self._last_process_start_rz: float | None = None
        self._last_process_end_pose: list[float] | None = None

    def prepare_workpiece_execution_plan(self, workpiece: dict, skip_debug_plot: bool = False) -> WorkpieceExecutionPlan:
        """Build and cache the execution plan for a paint workpiece."""
        if self._path_preparation_service is None:
            raise RuntimeError("Path preparation service is not available")

        generic_plan = self._path_preparation_service.build_execution_plan(workpiece, skip_debug_plot=skip_debug_plot)
        self._last_execution_plan = build_paint_contact_source_plan(generic_plan, self._contact_motion_config)
        return self._last_execution_plan

    def get_last_execution_plan(self) -> WorkpieceExecutionPlan | None:
        """Return the last paint execution plan prepared by this executor."""
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
        self._contact_motion_config = _normalize_contact_motion_config(
            motion_plane=self._contact_motion_config.motion_plane,
            translation_axis=self._contact_motion_config.translation_axis,
            pivot_side=self._contact_motion_config.paint_side,
            translation_direction=self._contact_motion_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._contact_motion_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._contact_motion_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._contact_motion_config.camera_to_tcp_y_offset)),
            rotation_direction_sign=_xz_ry_projection_rotation_sign(
                self._contact_motion_config.motion_plane,
                self._flip_xz_ry_execution_rotation_direction,
            ),
        )
        self._pickup_contact_motion_config = _normalize_contact_motion_config(
            motion_plane="xy_z_rz",
            translation_axis=self._pickup_contact_motion_config.translation_axis,
            pivot_side=self._pickup_contact_motion_config.paint_side,
            translation_direction=self._pickup_contact_motion_config.translation_direction,
            apply_camera_to_tcp_for_pickup=self._pickup_contact_motion_config.apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=float(getattr(robot_config, "camera_to_tcp_x_offset", self._pickup_contact_motion_config.camera_to_tcp_x_offset)),
            camera_to_tcp_y_offset=float(getattr(robot_config, "camera_to_tcp_y_offset", self._pickup_contact_motion_config.camera_to_tcp_y_offset)),
        )
        self._contact_motion_strategy = get_execution_plane_strategy(self._contact_motion_config.motion_plane)

    def _make_runtime_contact_motion_config(self, motion_plane: str) -> PaintSimulationConfig:
        """Build a projection config for a requested execution plane."""
        plane = str(motion_plane or "xy_z_rz").strip().lower()
        return _normalize_contact_motion_config(
            motion_plane=plane,
            translation_axis=self._configured_contact_translation_axis,
            pivot_side=self._configured_contact_side,
            translation_direction=self._configured_contact_translation_direction,
            apply_camera_to_tcp_for_pickup=self._apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=self._contact_motion_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=self._contact_motion_config.camera_to_tcp_y_offset,
            rotation_direction_sign=_xz_ry_projection_rotation_sign(
                plane,
                self._flip_xz_ry_execution_rotation_direction,
            ),
        )

    def _set_runtime_contact_motion_config(self, pivot_config: PaintSimulationConfig) -> None:
        """Switch the active projection config used by executor helper methods."""
        self._contact_motion_config = pivot_config
        self._contact_motion_strategy = get_execution_plane_strategy(pivot_config.motion_plane)

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        """Report the execution modes supported by the paint executor."""
        return ()

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
        return self.execute_paint_process(execution_plan)

    def _resolve_base_position(self) -> Optional[list[float]]:
        """Resolve the configured pivot/base pose used to project paint motion."""
        provider = self._base_position_provider
        if self._contact_motion_config.motion_plane == "xy_z_rz" and self._pickup_base_position_provider is not None:
            provider = self._pickup_base_position_provider
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
            resolved = [float(position[i]) for i in range(6 if len(position) >= 6 else len(position))]
        except (TypeError, ValueError):
            return None
        if abs(float(self._active_contact_base_z_offset_mm)) > 1e-9:
            while len(resolved) < 3:
                resolved.append(0.0)
            resolved[2] = float(resolved[2]) + float(self._active_contact_base_z_offset_mm)
        return resolved

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
        target_index = self._contact_motion_strategy.pivot_offset_position_index
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

    def _paint_start_staging_offset_pose(self, contact_pose: list[float]) -> list[float]:
        """Return the configured pre-paint staging offset pose."""
        return _paint_axis_staging_offset_pose(contact_pose, self._contact_motion_config)

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

    def get_projected_pivot_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        """Project center paths for each prepared execution job around the pivot pose."""
        self._refresh_runtime_config()
        base_pivot_pose = self._resolve_base_position()
        if base_pivot_pose is None or len(base_pivot_pose) < 3:
            return [], base_pivot_pose
        pickup_plan = self._pickup_transfer_planner.build_plan(execution_plan)
        return project_pivot_paths_for_editor(
            execution_plan=execution_plan,
            pivot_config=self._contact_motion_config,
            base_pivot_pose=base_pivot_pose,
            pickup_plan=pickup_plan,
            apply_pivot_offset=self._apply_pivot_offset,
            resolve_pivot_offset_mm=self._resolve_pivot_offset_mm,
            align_projected_path_to_pickup_plan=self._align_projected_path_to_pickup_plan,
            pivot_execution_command_path=self._paint_contact_command_path,
            project_motion_geometry=project_paint_contact_motion_continuous,
        )

    def get_pivot_motion_snapshots(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[np.ndarray]], list[float] | None]:
        """Return per-step projected shape snapshots for pivot motion plotting."""
        self._refresh_runtime_config()
        base_pivot_pose = self._resolve_base_position()
        if base_pivot_pose is None or len(base_pivot_pose) < 3:
            return [], base_pivot_pose
        pickup_plan = self._pickup_transfer_planner.build_plan(execution_plan)
        return project_pivot_motion_snapshots_for_editor(
            execution_plan=execution_plan,
            pivot_config=self._contact_motion_config,
            base_pivot_pose=base_pivot_pose,
            pickup_plan=pickup_plan,
            apply_pivot_offset=self._apply_pivot_offset,
            resolve_pivot_offset_mm=self._resolve_pivot_offset_mm,
            project_motion_geometry=project_paint_contact_motion_continuous,
        )


    def _build_paint_contact_path(
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
        """Project one prepared spline into the real paint-contact trajectory."""
        with timed_block(_logger, "pivot_path_prepare", label="resolve_base_and_offset"):
            pivot_pose = self._apply_pivot_offset(self._resolve_base_position(), pivot_offset_mm)
        if pivot_pose is None or len(pivot_pose) < 3:
            return None
        with timed_block(_logger, "pivot_path_prepare", label="project_execution_path"):
            pivot_path, snapshots, diagnostics = project_paint_contact_motion_continuous(
                spline,
                pivot_pose,
                self._contact_motion_config,
                anchor_xy=anchor_xy,
                source_rotation_deg=source_rotation_deg,
            )
        _logger.debug("Simulated pivot path has %d points", len(pivot_path))
        if align_start_to_zero_rz:
            with timed_block(_logger, "pivot_path_prepare", label="rebase_start_rotation"):
                pivot_path = rebase_contact_motion_path_to_zero_start_rotation(
                    pivot_path,
                    self._contact_motion_config,
                )
        return pivot_path, snapshots, diagnostics, list(pivot_pose)

    def execute_process_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        """Paint no longer supports direct/manual paint-contact path execution."""
        return False, "Direct paint path execution is not supported; use the paint process action"

    @timed_step(_logger, "pickup_phase", label_arg="label")
    def _move_pickup_phase(self, label: str, pose: list[float], *, velocity: float, acceleration: float) -> bool:
        """Execute one pickup-related robot move with explicit motion limits."""
        if velocity is None or acceleration is None:
            raise ValueError(
                f"Pickup phase '{label}' requires explicit velocity and acceleration"
            )
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
            velocity=velocity,
            acceleration=acceleration,
            wait_to_reach=True,
        )
        return ok

    @timed_step(_logger, "pickup_phase", label_arg="label")
    def _move_custom_pickup_sequence(self, label: str, segments: list[MotionSequenceSegment]) -> bool:
        """Execute an experimental custom pickup sequence with per-segment speed/accel."""
        _logger.info(
            "[PICKUP] %s tool=%d user=%d segments=%d",
            label,
            self._pickup_tool,
            self._pickup_user,
            len(segments),
        )
        move_sequence = getattr(self._robot_service, "move_custom_sequence", None)
        if not callable(move_sequence):
            _logger.info("[PICKUP] Custom motion sequence unavailable")
            return False
        return bool(
            move_sequence(
                segments=segments,
                tool=self._pickup_tool,
                user=self._pickup_user,
                wait_to_reach=True,
            )
        )

    def _paint_contact_staging_command_pose(self, pose: list[float], reference_pose: list[float]) -> list[float]:
        """Return the robot command pose for moving the held workpiece into XZ/RY pivot contact."""
        if self._contact_motion_config.motion_plane != "xz_y_ry":
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
            float(self._contact_motion_config.rotation_direction_sign),
        )
        return command_pose

    def _align_projected_path_to_pickup_plan(
        self,
        path: list[list[float]],
        pickup_plan: PickupTransferPlan | None,
    ) -> list[list[float]]:
        """Apply the same first-rotation alignment used before pivot execution."""
        if not path or pickup_plan is None:
            return [list(pose) for pose in path]
        rotation_index = self._contact_motion_config.rotation_index
        if len(path[0]) <= rotation_index or len(pickup_plan.staged_pose) <= rotation_index:
            return [list(pose) for pose in path]
        if self._contact_motion_config.motion_plane == "xy_z_rz":
            staged_rotation = float(pickup_plan.staged_pose[rotation_index])
            raw_start_rotation = float(path[0][rotation_index])
            rotation_shift = axis_equivalent_shift_degrees(staged_rotation, raw_start_rotation)
        elif self._contact_motion_config.motion_plane == "xz_y_ry":
            staged_rotation = float(pickup_plan.staged_pose[rotation_index])
            raw_start_rotation = float(path[0][rotation_index])
            rotation_shift = staged_rotation - raw_start_rotation
        else:
            rotation_shift = 0.0
        return _shift_path_rotation(path, rotation_index, rotation_shift)

    def _paint_contact_command_path(
        self,
        path: list[list[float]],
        *,
        pickup_plan: PickupTransferPlan | None = None,
    ) -> list[list[float]]:
        """Return robot command poses for XZ/RY pivot execution without changing planned geometry."""
        if not path:
            return []
        command_path = [list(pose) for pose in path]
        plan = pickup_plan or self._last_pickup_plan
        if (
            self._contact_motion_config.motion_plane == "xz_y_ry"
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
                float(self._contact_motion_config.rotation_direction_sign),
            )
        return command_path

    def _append_contact_retreat_waypoint(self, command_path: list[list[float]]) -> list[list[float]]:
        """Append an off-contact retreat waypoint to the paint trajectory command."""
        if not command_path:
            return []
        path_with_retreat = [list(pose) for pose in command_path]
        final_contact_pose = list(path_with_retreat[-1])
        retreat_pose = _paint_axis_staging_offset_pose(final_contact_pose, self._contact_motion_config)
        if np.allclose(
            np.asarray(final_contact_pose[:3], dtype=float),
            np.asarray(retreat_pose[:3], dtype=float),
            atol=1e-6,
        ):
            return path_with_retreat
        path_with_retreat.append(retreat_pose)
        _logger.info(
            "[PIVOT_PATH] appended off-pivot retreat waypoint: contact_pose=%s retreat_pose=%s",
            [round(float(v), 3) for v in final_contact_pose[:6]],
            [round(float(v), 3) for v in retreat_pose[:6]],
        )
        return path_with_retreat

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

    @timed_step(_logger, "prepare_dropoff_unwind")
    def _prepare_dropoff_joint6_unwind(self) -> tuple[bool, str]:
        """Move to the safe unwind orientation, then relieve Joint 6 before dropoff."""
        if self._configured_contact_motion_plane == "xz_y_ry":
            plan = self._last_pickup_plan
            if plan is None:
                return False, "Pivot paint finished, but no pickup plan is available for safe pre-dropoff unwind alignment"
            if not self._move_pickup_phase(
                "Returning to original orientation before dropoff unwind",
                plan.align_pose,
                velocity=PAINT_PROCESS_CONFIG.dropoff.release_align_vel_percent,
                acceleration=PAINT_PROCESS_CONFIG.dropoff.release_align_acc_percent,
            ):
                return False, "Pivot paint finished, but return to original orientation failed before dropoff unwind"
        if self._robot_service is None:
            return False, "Pivot paint finished, but robot service is not available for pre-dropoff Joint 6 unwind"
        _logger.info(
            "[DROPOFF] Unwinding Joint 6 before dropoff strategy vel=%.1f acc=%.1f queue_if_busy=%s",
            PAINT_PROCESS_CONFIG.navigation_return.unwind_vel_percent,
            PAINT_PROCESS_CONFIG.navigation_return.unwind_acc_percent,
            PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
        )
        ok = self._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
            vel=PAINT_PROCESS_CONFIG.navigation_return.unwind_vel_percent,
            acc=PAINT_PROCESS_CONFIG.navigation_return.unwind_acc_percent,
        )
        if not ok:
            return False, "Pivot paint finished, but Joint 6 unwind failed before dropoff"
        return True, ""

    def execute_paint_process(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Run the full paint process.

        Phase order:
        1. Pick up the workpiece.
        2. Lift and align the held workpiece to the paint axis.
        3. Change to the configured paint contact plane and stage at the first contact pose.
        4. Execute the paint-contact path against the fixed paint shaft.
        5. Optionally run the XY/RZ edge-cleanup pass after a safe unwind.
        6. Move to a safe pre-dropoff orientation and unwind Joint 6.
        7. Execute the configured dropoff strategy and release the workpiece.
        8. Run the post-process return callback.
        """
        with timing_session("paint_process") as recorder:
            started = perf_counter()
            total_waypoints = 0
            result: tuple[bool, str]

            # Phase 1: pickup, lift, align, change plane, and stage at first contact.
            ok, msg = self._pickup.execute(prepared_workpiece)
            if not ok:
                _logger.info("[TIMING] paint_process success=false stage=pickup total_elapsed_s=%.3f", elapsed_s(started))
                result = (False, msg)
            else:
                with timed_block(_logger, "paint_contact_cleanup_dropoff"):
                    # Phase 2: execute the primary paint-contact path.
                    ok, msg, total_waypoints = self._paint_contact.execute(prepared_workpiece)
                    if not ok:
                        _logger.info("[TIMING] paint_process success=false stage=contact total_elapsed_s=%.3f", elapsed_s(started))
                        result = (False, msg)
                    elif self._edge_cleanup.should_run_after_xz_ry():
                        # Phase 3: optional edge cleanup in XY/RZ after safe cleanup unwind.
                        ok, msg, cleanup_waypoints = self._edge_cleanup.execute_after_unwind(prepared_workpiece, started)
                        total_waypoints += cleanup_waypoints
                        result = (False, msg) if not ok else (True, "")
                    else:
                        result = (True, "")

                    if result[0]:
                        # Phase 4: return to safe orientation and unwind Joint 6 before dropoff.
                        ok, msg = self._prepare_dropoff_joint6_unwind()
                        if not ok:
                            _logger.info("[TIMING] paint_process success=false stage=prepare_dropoff_unwind total_elapsed_s=%.3f", elapsed_s(started))
                            result = (False, msg)

                    if result[0]:
                        # Phase 5: execute the configured dropoff strategy and release the part.
                        ok, msg = self._dropoff.execute(prepared_workpiece)
                        if not ok:
                            _logger.info("[TIMING] paint_process success=false stage=pre_release_dropoff total_elapsed_s=%.3f", elapsed_s(started))
                            result = (False, msg)

                    if result[0]:
                        _logger.info(
                            "[EXECUTE] Paint process completed: jobs=%d total_waypoints=%d",
                            len(prepared_workpiece.execution_jobs),
                            total_waypoints,
                        )
                        result = (True, (
                            f"Paint process completed "
                            f"for {len(prepared_workpiece.execution_jobs)} path(s), {total_waypoints} waypoints"
                        ))
                with timed_block(_logger, "return_after_paint_process"):
                    # Phase 6: return the robot to its configured post-process position.
                    if self._post_execute_callback is None:
                        _logger.info("[EXECUTE] Post-execute return skipped: callback not configured")
                    else:
                        try:
                            return_started = perf_counter()
                            moved = bool(self._post_execute_callback())
                        except Exception:
                            _logger.exception("[EXECUTE] Post-execute callback failed")
                            _logger.info(
                                "[TIMING] paint_process success=false stage=post_return total_elapsed_s=%.3f",
                                elapsed_s(started),
                            )
                            result = (False, "Paint process finished, but return-to-calibration failed") if result[0] else (
                                False,
                                f"{result[1]}; additionally, return-to-calibration failed",
                            )
                        else:
                            if not moved:
                                _logger.info(
                                    "[TIMING] paint_process success=false stage=post_return return_elapsed_s=%.3f total_elapsed_s=%.3f",
                                    elapsed_s(return_started),
                                    elapsed_s(started),
                                )
                                result = (False, "Paint process finished, but return-to-calibration failed") if result[0] else (
                                    False,
                                    f"{result[1]}; additionally, return-to-calibration failed",
                                )

            recorder.record(
                step="paint_process",
                label="",
                success=result[0],
                elapsed_s=elapsed_s(started),
                started_at=started,
                ended_at=perf_counter(),
            )
            return result
