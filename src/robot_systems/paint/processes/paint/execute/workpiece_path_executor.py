from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Optional

import numpy as np

from src.engine.geometry.planar import (
    axis_equivalent_shift_degrees,
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
    PaintProcessConfig,
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

_STAGING_Z_OFFSET_MM = 0
_STAGING_PAINT_AXIS_OFFSET_MM = 80.0
_PICKUP_RESUME_WAYPOINT_TOLERANCE_MM = 2.0


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
    cleanup_base_position_provider: Optional[Callable[[], Optional[list[float]]]] = None
    dropoff_position_provider: Optional[Callable[[], Optional[list[float]]]] = None
    calibration_position_provider: Optional[Callable[[], Optional[list[float]]]] = None
    post_execute_callback: Optional[Callable[[], bool]] = None
    robot_config_provider: Optional[Callable[[], object]] = None
    vacuum_pump: object | None = None
    paint_process_config_service: object | None = None

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
            cleanup_base_position_provider=legacy_options.get("cleanup_base_position_provider"),
            dropoff_position_provider=legacy_options.get("dropoff_position_provider"),
            calibration_position_provider=legacy_options.get("calibration_position_provider"),
            post_execute_callback=legacy_options.get("post_execute_callback"),
            robot_config_provider=legacy_options.get("robot_config_provider"),
            vacuum_pump=legacy_options.get("vacuum_pump"),
            paint_process_config_service=legacy_options.get("paint_process_config_service"),
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
        self._cleanup_base_position_provider = dependencies.cleanup_base_position_provider
        self._dropoff_position_provider = dependencies.dropoff_position_provider
        self._calibration_position_provider = dependencies.calibration_position_provider
        self._post_execute_callback = dependencies.post_execute_callback
        self._robot_config_provider = dependencies.robot_config_provider
        self._vacuum_pump = dependencies.vacuum_pump
        self._paint_process_config_service = dependencies.paint_process_config_service

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
        self._dropoff_unwind_prepared: bool = False
        self._last_safe_travel_error: str = ""
        self._paint_process_config_snapshot: PaintProcessConfig = PAINT_PROCESS_CONFIG
        self._active_execution_control = None
        self._ordered_chain_resume_start_index: int | None = None
        self._ordered_chain_interrupted_by_pause: bool = False

    def prepare_workpiece_execution_plan(self, workpiece: dict, skip_debug_plot: bool = False) -> WorkpieceExecutionPlan:
        """Build and cache the execution plan for a paint workpiece."""
        if self._path_preparation_service is None:
            raise RuntimeError("Path preparation service is not available")

        self._refresh_paint_process_config_snapshot()
        self._apply_paint_process_contact_config()
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

    def _refresh_paint_process_config_snapshot(self) -> None:
        service = self._paint_process_config_service
        if service is None:
            self._paint_process_config_snapshot = PAINT_PROCESS_CONFIG
            return
        try:
            self._paint_process_config_snapshot = service.get_snapshot()
            self._enable_vacuum_pump = bool(self._paint_process_config_snapshot.enable_vacuum_pump)
        except Exception:
            _logger.debug("[PAINT_CONFIG] Failed to refresh paint process settings", exc_info=True)
            self._paint_process_config_snapshot = PAINT_PROCESS_CONFIG

    def _paint_process_config(self) -> PaintProcessConfig:
        return self._paint_process_config_snapshot or PAINT_PROCESS_CONFIG

    def _apply_paint_process_contact_config(self) -> None:
        """Apply the latest Paint process settings to the active contact-motion profile."""
        config = self._paint_process_config()
        plane = str(config.pivot_motion_plane or self._configured_contact_motion_plane).strip().lower()
        translation_axis = str(config.pivot_axis or self._configured_contact_translation_axis).strip().lower()
        side = str(config.pivot_contact_side or self._configured_contact_side).strip().lower()
        direction = str(config.pivot_direction or self._configured_contact_translation_direction).strip().lower()
        mirror_execution_rotation = (
            plane == "xz_y_ry"
            and bool(config.mirror_xz_ry_execution_rotation_value)
        )

        self._configured_contact_motion_plane = plane
        self._configured_contact_translation_axis = translation_axis
        self._configured_contact_side = side
        self._configured_contact_translation_direction = direction
        self._apply_camera_to_tcp_for_pickup = bool(config.apply_camera_to_tcp_for_pickup)
        self._flip_xz_ry_execution_rotation_direction = mirror_execution_rotation
        self._contact_motion_config = _normalize_contact_motion_config(
            motion_plane=plane,
            translation_axis=translation_axis,
            pivot_side=side,
            translation_direction=direction,
            apply_camera_to_tcp_for_pickup=self._apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=self._contact_motion_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=self._contact_motion_config.camera_to_tcp_y_offset,
            rotation_direction_sign=_xz_ry_projection_rotation_sign(
                plane,
                self._flip_xz_ry_execution_rotation_direction,
            ),
        )
        self._pickup_contact_motion_config = _normalize_contact_motion_config(
            motion_plane="xy_z_rz",
            translation_axis=translation_axis,
            pivot_side=side,
            translation_direction=direction,
            apply_camera_to_tcp_for_pickup=self._apply_camera_to_tcp_for_pickup,
            camera_to_tcp_x_offset=self._pickup_contact_motion_config.camera_to_tcp_x_offset,
            camera_to_tcp_y_offset=self._pickup_contact_motion_config.camera_to_tcp_y_offset,
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

    @timed_step(_logger, "magazine_pickup_to_calibration_release")
    def execute_pickup_and_release_at_calibration(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        """Pick up the prepared contour and release it at the calibration movement group."""
        calibration_pose = self._resolve_calibration_position()
        if calibration_pose is None:
            return False, "Calibration movement group is not configured"
        return self.execute_pickup_and_release_at_position(
            prepared_workpiece,
            calibration_pose,
            release_label="calibration",
        )



    @timed_step(_logger, "pickup_target_to_position_release")
    def execute_pickup_target_and_release_at_position(
        self,
        *,
        pickup_xy: tuple[float, float] | list[float],
        pickup_rz: float,
        pickup_base_pose: list[float],
        release_pose: list[float],
        workpiece_height_mm: float = 0.0,
        release_label: str = "release",
        resume_from_current_pose: bool = False,
    ) -> tuple[bool, str]:
        """Pick up a simple resolved target and release it at an explicit pose."""
        self._refresh_paint_process_config_snapshot()
        self._apply_paint_process_contact_config()
        self._refresh_runtime_config()
        if pickup_xy is None or len(pickup_xy) < 2:
            return False, "Pickup target XY is not configured"
        if pickup_base_pose is None or len(pickup_base_pose) < 6:
            return False, "Pickup base pose is not configured"
        if release_pose is None or len(release_pose) < 6:
            return False, f"{release_label.capitalize()} pose is not configured"

        pickup_motion = self._paint_process_config().pickup_motion
        pickup_z = self._pickup_z_mm
        if pickup_z is None:
            pickup_z = (
                self._pickup_safety_z_min_mm
                + float(workpiece_height_mm or 0.0)
                + pickup_motion.contact_offset_mm
            )

        pickup_x = float(pickup_xy[0])
        pickup_y = float(pickup_xy[1])
        pickup_rx = float(pickup_base_pose[3])
        pickup_ry = float(pickup_base_pose[4])
        pickup_rz = float(pickup_rz)
        approach_pose = [
            pickup_x,
            pickup_y,
            float(pickup_z) + pickup_motion.approach_offset_mm,
            pickup_rx,
            pickup_ry,
            pickup_rz,
        ]
        pickup_pose = [pickup_x, pickup_y, float(pickup_z), pickup_rx, pickup_ry, pickup_rz]
        lift_pose = [
            pickup_x,
            pickup_y,
            float(pickup_z) + min(
                pickup_motion.initial_lift_clearance_mm,
                pickup_motion.approach_offset_mm,
            ),
            pickup_rx,
            pickup_ry,
            pickup_rz,
        ]

        _logger.info(
            "[MAGAZINE_LOAD] pickup target xy=(%.3f, %.3f) rz=%.3f workpiece_height=%.3f pickup_z=%.3f safety_z_min=%.3f",
            pickup_x,
            pickup_y,
            pickup_rz,
            float(workpiece_height_mm or 0.0),
            float(pickup_z),
            self._pickup_safety_z_min_mm,
        )

        transfer_waypoints = (
            (
                "Moving to magazine pickup approach pose",
                approach_pose,
                pickup_motion.approach_vel_percent,
                pickup_motion.approach_acc_percent,
                "linear",
            ),
            (
                "Descending to magazine pickup pose",
                pickup_pose,
                pickup_motion.descend_vel_percent,
                pickup_motion.descend_acc_percent,
                "linear",
            ),
            (
                "Lifting magazine workpiece",
                lift_pose,
                pickup_motion.lift_align_vel_percent,
                pickup_motion.lift_align_acc_percent,
                "ptp",
            ),
        )
        velocity, acceleration = self._magazine_transfer_to_calibration_speed()
        release_move_label = f"Moving picked workpiece to {release_label} release pose"
        transfer_waypoints = transfer_waypoints + (
            (
                release_move_label,
                list(release_pose),
                velocity,
                acceleration,
                "ptp",
            ),
        )

        ordered_segments = []

        for index, (
                label,
                pose,
                velocity,
                acceleration,
                move_type,
        ) in enumerate(transfer_waypoints):

            blend_r = 0.0

            #
            # Blend "Lifting magazine workpiece"
            # into the following release PTP.
            #
            if (
                    label == "Lifting magazine workpiece"
                    and index + 1 < len(transfer_waypoints)
            ):
                blend_r = 20.0

            ordered_segments.append(
                {
                    "type": move_type,
                    "label": label,
                    "position": list(pose),
                    "vel": float(velocity),
                    "acc": float(acceleration),
                    "blendR": blend_r,
                }
            )

        if resume_from_current_pose:
            ordered_segments = self._trim_ordered_pickup_segments_from_current_pose(ordered_segments)
            transfer_waypoints = tuple(
                (
                    str(segment.get("label", "")),
                    list(segment["position"]),
                    float(segment["vel"]),
                    float(segment["acc"]),
                    str(segment.get("type", "ptp")),
                )
                for segment in ordered_segments
            )
        if not ordered_segments:
            _logger.info("[PICKUP] Ordered magazine pickup-to-release sequence already at final target")
        else:
            ok, msg = self._execute_pickup_transfer_sequence(
                "Ordered magazine pickup-to-release sequence",
                ordered_segments,
                transfer_waypoints,
                turn_vacuum_on=True,
            )
            if not ok:
                return False, msg or f"Move to {release_label} release pose failed"

        ok, msg = self._turn_vacuum_off()
        if not ok:
            return False, msg
        return True, f"Workpiece transferred to {release_label}"

    def _trim_ordered_pickup_segments_from_current_pose(self, segments: list[dict]) -> list[dict]:
        """Skip already-passed pickup waypoints after pause/resume.

        Ordered-chain execution starts from the robot's current pose. On resume we
        keep the waypoint currently being approached and later waypoints, instead
        of re-sending earlier pickup targets and making the robot backtrack.
        """
        if not segments:
            return []

        current = self._read_current_robot_pose()
        if current is None:
            _logger.warning("[PICKUP] Resume requested but current robot pose is unavailable; reusing full sequence")
            return segments

        target_positions = []
        for segment in segments:
            position = segment.get("position") if isinstance(segment, dict) else None
            if not position or len(position) < 3:
                return segments
            target_positions.append([float(position[0]), float(position[1]), float(position[2])])

        current_xyz = np.array(current[:3], dtype=float)
        targets = [np.array(position[:3], dtype=float) for position in target_positions]

        nearest_target_index = min(
            range(len(targets)),
            key=lambda index: float(np.linalg.norm(current_xyz - targets[index])),
        )
        if float(np.linalg.norm(current_xyz - targets[nearest_target_index])) <= _PICKUP_RESUME_WAYPOINT_TOLERANCE_MM:
            start_index = min(nearest_target_index + 1, len(segments))
            _logger.info(
                "[PICKUP] Resume from current pose near waypoint %d; remaining segments=%d",
                nearest_target_index,
                len(segments) - start_index,
            )
            return segments[start_index:]

        best_index = 0
        best_distance = float("inf")
        for index in range(len(targets)):
            if index == 0:
                distance = float(np.linalg.norm(current_xyz - targets[index]))
            else:
                distance = self._point_to_segment_distance(current_xyz, targets[index - 1], targets[index])
            if distance < best_distance:
                best_distance = distance
                best_index = index

        _logger.info(
            "[PICKUP] Resume from current pose; continuing toward waypoint %d/%d distance_to_path=%.3fmm",
            best_index,
            len(segments) - 1,
            best_distance,
        )
        return segments[best_index:]

    def _read_current_robot_pose(self) -> list[float] | None:
        get_current_position = getattr(self._robot_service, "get_current_position", None)
        if not callable(get_current_position):
            return None
        try:
            pose = get_current_position()
        except Exception:
            _logger.warning("[PICKUP] Failed to read current robot pose for resume", exc_info=True)
            return None
        if not pose or len(pose) < 3:
            return None
        try:
            return [float(value) for value in pose]
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _point_to_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
        segment = end - start
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-9:
            return float(np.linalg.norm(point - end))
        t = float(np.dot(point - start, segment) / length_sq)
        t = max(0.0, min(1.0, t))
        projected = start + t * segment
        return float(np.linalg.norm(point - projected))

    @staticmethod
    def _read_provider_position(provider: Optional[Callable[[], Optional[list[float]]]]) -> Optional[list[float]]:
        """Read and normalize a movement-group position provider result."""
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

    def _resolve_base_position(self) -> Optional[list[float]]:
        """Resolve the configured pivot/base pose used to project paint motion."""
        provider = self._base_position_provider
        if self._contact_motion_config.motion_plane == "xy_z_rz" and self._pickup_base_position_provider is not None:
            provider = self._pickup_base_position_provider
        resolved = self._read_provider_position(provider)
        if resolved is None:
            return None
        if abs(float(self._active_contact_base_z_offset_mm)) > 1e-9:
            while len(resolved) < 3:
                resolved.append(0.0)
            resolved[2] = float(resolved[2]) + float(self._active_contact_base_z_offset_mm)
        return resolved

    def _resolve_cleanup_base_position(self) -> Optional[list[float]]:
        """Resolve the dedicated XY/RZ cleanup base pose."""
        return self._read_provider_position(self._cleanup_base_position_provider)

    def _resolve_dropoff_position(self) -> Optional[list[float]]:
        """Resolve the configured movement-group dropoff pose."""
        return self._read_provider_position(self._dropoff_position_provider)

    def _resolve_safe_travel_position(self) -> Optional[list[float]]:
        """Resolve the optional carried-workpiece safe travel waypoint."""
        positions = self._resolve_safe_travel_positions()
        return positions[0] if positions else None

    def _resolve_safe_travel_positions(self) -> list[list[float]]:
        """Resolve optional carried-workpiece safe travel waypoints."""
        return [list(item["position"]) for item in self._resolve_safe_travel_waypoints()]

    def _resolve_safe_travel_waypoints(self) -> list[dict]:
        """Resolve optional carried-workpiece safe travel waypoints with motion tuning."""
        self._last_safe_travel_error = ""
        config = self._paint_process_config().safe_travel
        if not bool(config.enabled):
            return []
        motion = self._paint_process_config().pickup_motion
        waypoints = self._read_configured_waypoints(
            getattr(config, "positions", []),
            getattr(config, "position", []),
            float(motion.stage_transition_vel_percent),
            float(motion.stage_transition_acc_percent),
        )
        if not waypoints:
            self._last_safe_travel_error = "Safe travel is enabled but no valid 6-axis waypoint is configured"
            _logger.warning("[PICKUP] %s", self._last_safe_travel_error)
        return waypoints

    @staticmethod
    def _read_configured_pose(position: object) -> Optional[list[float]]:
        if isinstance(position, dict):
            position = position.get("position", position.get("pose", []))
        if not position:
            return None
        try:
            values = [float(value) for value in list(position)[:6]]
        except (TypeError, ValueError):
            return None
        return values if len(values) >= 6 else None

    @classmethod
    def _read_configured_poses(cls, positions: object, legacy_position: object = None) -> list[list[float]]:
        resolved: list[list[float]] = []
        if positions:
            try:
                raw_positions = list(positions)
            except TypeError:
                raw_positions = []
            for item in raw_positions:
                pose = cls._read_configured_pose(item)
                if pose is not None:
                    resolved.append(pose)
        if resolved:
            return resolved
        legacy = cls._read_configured_pose(legacy_position)
        return [legacy] if legacy is not None else []

    @classmethod
    def _read_configured_waypoints(
        cls,
        positions: object,
        legacy_position: object = None,
        default_vel: float = 50.0,
        default_acc: float = 20.0,
    ) -> list[dict]:
        resolved: list[dict] = []
        if positions:
            try:
                raw_positions = list(positions)
            except TypeError:
                raw_positions = []
            for item in raw_positions:
                waypoint = cls._read_configured_waypoint(item, default_vel, default_acc)
                if waypoint is not None:
                    resolved.append(waypoint)
        if resolved:
            return resolved
        legacy = cls._read_configured_waypoint(legacy_position, default_vel, default_acc)
        return [legacy] if legacy is not None else []

    @classmethod
    def _read_configured_waypoint(cls, value: object, default_vel: float, default_acc: float) -> dict | None:
        pose = cls._read_configured_pose(value)
        if pose is None:
            return None
        vel = float(default_vel)
        acc = float(default_acc)
        if isinstance(value, dict):
            try:
                vel = float(value.get("vel_percent", default_vel))
                acc = float(value.get("acc_percent", default_acc))
            except (TypeError, ValueError):
                vel = float(default_vel)
                acc = float(default_acc)
        else:
            try:
                raw = list(value)
                if len(raw) >= 8:
                    vel = float(raw[6])
                    acc = float(raw[7])
            except (TypeError, ValueError):
                pass
        return {"position": pose, "vel_percent": vel, "acc_percent": acc}

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
        self._refresh_paint_process_config_snapshot()
        self._apply_paint_process_contact_config()
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
        self._refresh_paint_process_config_snapshot()
        self._apply_paint_process_contact_config()
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
        while True:
            ok = self._robot_service.move_ptp(
                position=pose,
                tool=self._pickup_tool,
                user=self._pickup_user,
                velocity=velocity,
                acceleration=acceleration,
                wait_to_reach=True,
            )
            if ok:
                return True
            if not self._resume_after_interrupted_non_contact_motion(label):
                return False

    @timed_step(_logger, "pickup_phase", label_arg="label")
    def _move_ordered_pickup_sequence(self, label: str, segments: list[dict]) -> bool:
        """Execute a pickup sequence as ordered linear motion segments."""
        _logger.info(
            "[PICKUP] %s tool=%d user=%d segments=%d",
            label,
            self._pickup_tool,
            self._pickup_user,
            len(segments),
        )
        execute_chain = getattr(self._robot_service, "execute_ordered_motion_chain", None)
        if not callable(execute_chain):
            _logger.info("[PICKUP] Ordered motion chain unavailable")
            return False
        active_segments = list(segments)
        while active_segments:
            result = execute_chain(
                segments=active_segments,
                tool=self._pickup_tool,
                user=self._pickup_user,
                blocking=True,
            )
            if result in (0, True, None):
                return True
            if not self._resume_after_interrupted_non_contact_motion(label):
                return False
            active_segments = self._trim_ordered_pickup_segments_from_current_pose(active_segments)
        return True

    def _execute_pickup_transfer_sequence(
        self,
        ordered_label: str,
        ordered_segments: list[dict],
        transfer_waypoints: tuple[tuple[str, list[float], float, float, str], ...],
        *,
        turn_vacuum_on: bool,
    ) -> tuple[bool, str]:
        """Turn vacuum on, then execute the ordered pickup transfer."""
        execute_chain = getattr(self._robot_service, "execute_ordered_motion_chain", None)
        if not callable(execute_chain):
            return False, "Ordered motion chain is unavailable"

        if turn_vacuum_on:
            ok, msg = self._turn_vacuum_on()
            if not ok:
                return False, msg
        if not self._move_ordered_pickup_sequence(ordered_label, ordered_segments):
            return False, f"{ordered_label} failed"
        return True, ""

    def _execute_ordered_segments_with_pickup_vacuum_boundary(
        self,
        ordered_label: str,
        segments: list[dict],
        *,
        turn_vacuum_on: bool,
    ) -> bool:
        if turn_vacuum_on:
            ok, _msg = self._turn_vacuum_on()
            if not ok:
                return False
        if not self._move_ordered_pickup_sequence(ordered_label, segments):
            return False
        return True

    def pause_current_execution(self) -> None:
        control = self._active_execution_control
        if control is not None and getattr(control, "in_protected_phase", lambda: False)():
            return
        ordered_status = self._read_ordered_motion_chain_status()
        if self._ordered_motion_chain_segment_is_protected(ordered_status):
            _logger.info("[EXECUTE] Paint pause requested during protected ordered segment; deferring stop")
            return
        self._ordered_chain_resume_start_index = self._ordered_motion_chain_resume_index(ordered_status)
        self._ordered_chain_interrupted_by_pause = True
        stop_motion = getattr(self._robot_service, "stop_motion", None)
        if callable(stop_motion):
            try:
                stop_motion()
            except Exception:
                _logger.exception("[EXECUTE] Failed to stop robot motion during paint pause")

    def _read_ordered_motion_chain_status(self) -> dict | None:
        get_status = getattr(self._robot_service, "get_execution_status", None)
        if not callable(get_status):
            return None
        try:
            status = get_status()
        except Exception:
            _logger.exception("[EXECUTE] Failed to read ordered motion status during paint pause")
            return None
        if not isinstance(status, dict):
            return None
        ordered = status.get("ordered_motion_chain")
        if not isinstance(ordered, dict):
            return None
        return ordered

    @staticmethod
    def _ordered_motion_chain_segment_is_protected(ordered: dict | None) -> bool:
        if not isinstance(ordered, dict):
            return False
        return bool(
            ordered.get("active")
            and ordered.get("phase") == "executing"
            and ordered.get("current_segment_protected")
        )

    @staticmethod
    def _ordered_motion_chain_resume_index(ordered: dict | None) -> int:
        if not isinstance(ordered, dict) or not ordered.get("active"):
            return 0
        try:
            index = int(ordered.get("current_segment_index"))
        except (TypeError, ValueError):
            return 0
        return max(0, index)

    def _resume_after_interrupted_non_contact_motion(self, label: str) -> bool:
        control = self._active_execution_control
        pause_requested = getattr(control, "pause_requested", None)
        interrupted_by_pause = self._ordered_chain_interrupted_by_pause
        if (not callable(pause_requested) or not pause_requested()) and not interrupted_by_pause:
            return False
        _logger.info("[EXECUTE] Paused during non-contact motion '%s'; waiting to resume", label)
        return self._wait_for_paint_resume(control)

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
        if self._dropoff_unwind_prepared:
            _logger.info("[DROPOFF] Pre-dropoff align/unwind already completed by ordered cleanup chain")
            return True, ""
        config = self._paint_process_config()
        safe_waypoints = self._resolve_dropoff_safe_travel_waypoints()
        if bool(config.dropoff_safe_travel.enabled):
            if not safe_waypoints:
                return False, "Pivot paint finished, but paint-to-dropoff safe travel waypoints are not configured"
            for index, safe_waypoint in enumerate(safe_waypoints, start=1):
                if not self._move_pickup_phase(
                    f"Moving through paint-to-dropoff safe travel waypoint {index}",
                    safe_waypoint["position"],
                    velocity=float(safe_waypoint["vel_percent"]),
                    acceleration=float(safe_waypoint["acc_percent"]),
                ):
                    return False, "Pivot paint finished, but paint-to-dropoff safe travel move failed"
        if self._should_prepare_dropoff_align_before_unwind():
            align_pose = self._resolve_dropoff_align_pose()
            if align_pose is None:
                return False, "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment"
            if not self._move_pickup_phase(
                "Moving to dropoff pose before unwind",
                align_pose,
                velocity=config.dropoff.release_align_vel_percent,
                acceleration=config.dropoff.release_align_acc_percent,
            ):
                return False, "Pivot paint finished, but move to dropoff pose failed before unwind"
        elif self._configured_contact_motion_plane == "xz_y_ry":
            return False, "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment"
        if self._robot_service is None:
            return False, "Pivot paint finished, but robot service is not available for pre-dropoff Joint 6 unwind"
        _logger.info(
            "[DROPOFF] Unwinding Joint 6 before dropoff strategy vel=%.1f acc=%.1f queue_if_busy=%s",
            config.navigation_return.unwind_vel_percent,
            config.navigation_return.unwind_acc_percent,
            PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
        )
        ok = self._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
            vel=config.navigation_return.unwind_vel_percent,
            acc=config.navigation_return.unwind_acc_percent,
        )
        if not ok:
            return False, "Pivot paint finished, but Joint 6 unwind failed before dropoff"
        return True, ""

    def _should_return_to_calibration_between_xy_rz_pickup_and_pivot(self) -> bool:
        """Return whether pickup must pass through calibration before pivot staging."""
        return False

    def _should_prepare_dropoff_align_before_unwind(self) -> bool:
        """Return whether the held part must move to a separate dropoff pose before unwind."""
        if self._dropoff_strategy_name() == "movement_group":
            return self._resolve_dropoff_release_pose() is not None
        return self._configured_contact_motion_plane == "xz_y_ry" and self._resolve_dropoff_release_pose() is not None

    def _resolve_dropoff_safe_travel_position(self) -> list[float] | None:
        """Resolve the optional carried-workpiece safe waypoint before entering dropoff."""
        positions = self._resolve_dropoff_safe_travel_positions()
        return positions[0] if positions else None

    def _resolve_dropoff_safe_travel_positions(self) -> list[list[float]]:
        """Resolve optional carried-workpiece safe waypoints before entering dropoff."""
        return [list(item["position"]) for item in self._resolve_dropoff_safe_travel_waypoints()]

    def _resolve_dropoff_safe_travel_waypoints(self) -> list[dict]:
        """Resolve optional carried-workpiece safe waypoints before entering dropoff with motion tuning."""
        config = self._paint_process_config().dropoff_safe_travel
        if not bool(config.enabled):
            return []
        dropoff = self._paint_process_config().dropoff
        return self._read_configured_waypoints(
            getattr(config, "positions", []),
            getattr(config, "position", []),
            float(dropoff.release_align_vel_percent),
            float(dropoff.release_align_acc_percent),
        )

    def _should_release_at_current_dropoff_pose(self) -> bool:
        """Return whether release should happen at the current post-paint retreat pose."""
        return (
            self._configured_contact_motion_plane == "xy_z_rz"
            and self._dropoff_strategy_name() == "pickup_origin"
        )

    def _calibration_return_speed(self) -> tuple[float, float]:
        config = self._paint_process_config()
        return (
            float(config.navigation_return.calibration_move_vel_percent),
            float(config.navigation_return.calibration_move_acc_percent),
        )

    def _magazine_transfer_to_calibration_speed(self) -> tuple[float, float]:
        config = self._paint_process_config()
        return (
            float(config.magazine_load.transfer_to_calibration_vel_percent),
            float(config.magazine_load.transfer_to_calibration_acc_percent),
        )

    def _resolve_calibration_position(self) -> list[float] | None:
        if self._calibration_position_provider is None:
            return None
        try:
            position = self._calibration_position_provider()
        except Exception:
            _logger.exception("[PICKUP] Failed to resolve calibration position")
            return None
        if position is None:
            return None
        return list(position)

    @timed_step(_logger, "xy_rz_pickup_to_calibration_before_pivot")
    def _return_to_calibration_before_xy_rz_pivot(self) -> tuple[bool, str]:
        """Move the held part to calibration after pickup alignment and before pivot staging."""
        if not self._should_return_to_calibration_between_xy_rz_pickup_and_pivot():
            return True, ""
        position = self._resolve_calibration_position()
        if position is None:
            return False, "Pickup aligned, but calibration position is not configured before XY/RZ pivot"
        velocity, acceleration = self._calibration_return_speed()
        if not self._move_pickup_phase(
            "Returning to calibration before XY/RZ pivot",
            position,
            velocity=velocity,
            acceleration=acceleration,
        ):
            return False, "Pickup aligned, but return to calibration failed before XY/RZ pivot"
        return True, ""

    @timed_step(_logger, "xy_rz_cleanup_calibration_return")
    def _return_to_calibration_and_unwind_before_xy_rz_cleanup(self) -> tuple[bool, str]:
        """Move to calibration after XY/RZ paint, then unwind Joint 6 there before cleanup."""
        if self._configured_contact_motion_plane != "xy_z_rz":
            return True, ""
        position = self._resolve_calibration_position()
        if position is None:
            return False, "XY/RZ paint succeeded, but calibration position is not configured before cleanup"
        velocity, acceleration = self._calibration_return_speed()
        if not self._move_pickup_phase(
            "Returning to calibration before XY/RZ cleanup unwind",
            position,
            velocity=velocity,
            acceleration=acceleration,
        ):
            return False, "XY/RZ paint succeeded, but return to calibration failed before edge cleanup"
        ok, msg = self._edge_cleanup.unwind_joint6_before_cleanup(
            failure_context="XY/RZ paint succeeded, but Joint 6 unwind failed at calibration before edge cleanup"
        )
        return ok, msg

    def _dropoff_align_pose_near_reference(
        self,
        align_pose: list[float],
        reference_pose: list[float] | None = None,
    ) -> list[float]:
        """Return a dropoff align pose without an XY/RZ wrap jump from the previous command."""
        pose = list(align_pose)
        reference = reference_pose or self._last_process_end_pose
        if (
            self._configured_contact_motion_plane == "xy_z_rz"
            and reference is not None
            and len(pose) >= 6
            and len(reference) >= 6
        ):
            pose[5] = unwrap_degrees(float(reference[5]), float(pose[5]))
        return pose

    def _dropoff_strategy_name(self) -> str:
        """Return the active dropoff strategy key from live process settings."""
        return str(self._paint_process_config().dropoff.strategy or "pickup_origin").strip().lower()

    def _resolve_dropoff_release_pose(self) -> list[float] | None:
        """Resolve the target pose where the held part should be released."""
        if self._dropoff_strategy_name() == "movement_group":
            return self._resolve_dropoff_position()
        if self._last_pickup_plan is not None:
            return list(self._last_pickup_plan.align_pose)
        return None

    def _resolve_dropoff_align_pose(self, reference_pose: list[float] | None = None) -> list[float] | None:
        """Resolve the release pose adjusted to avoid an avoidable rotation wrap."""
        pose = self._resolve_dropoff_release_pose()
        if pose is None:
            return None
        return self._dropoff_align_pose_near_reference(pose, reference_pose)

    def _apply_distributed_dropoff_unwind(
        self,
        poses: list[list[float]],
        start_pose: list[float] | None,
    ) -> list[list[float]]:
        """
        Progressively shift the active rotation component by whole-turn
        equivalents so Joint 6 can unwind while travelling toward dropoff.

        Configured XYZ positions are preserved.

        Nominal waypoint rotations are first unwrapped onto one continuous
        branch without considering the unwind offset. The unwind offset is then
        added progressively according to cumulative XYZ travel distance.

        Keeping those two operations separate prevents later waypoints from
        selecting the opposite +/-360 degree branch and reversing the unwind.
        """
        if not poses:
            return []

        adjusted = [
            list(pose)
            for pose in poses
        ]

        if start_pose is None or len(start_pose) < 6:
            return adjusted

        rotation_index = int(
            self._contact_motion_config.rotation_index
        )

        if rotation_index < 0:
            return adjusted

        if len(start_pose) <= rotation_index:
            return adjusted

        if any(
            len(pose) <= rotation_index
            for pose in adjusted
        ):
            return adjusted

        start_rotation_deg = float(
            start_pose[rotation_index]
        )

        #
        # Build the nominal route on one continuous rotation branch.
        # Do NOT include the unwind correction while choosing this branch.
        #
        nominal_continuous_rotations: list[float] = []
        previous_nominal_rotation_deg = (
            start_rotation_deg
        )

        for pose in adjusted:
            nominal_rotation_deg = float(
                pose[rotation_index]
            )

            continuous_rotation_deg = (
                unwrap_degrees(
                    previous_nominal_rotation_deg,
                    nominal_rotation_deg,
                )
            )

            nominal_continuous_rotations.append(
                continuous_rotation_deg
            )

            previous_nominal_rotation_deg = (
                continuous_rotation_deg
            )

        if not nominal_continuous_rotations:
            return adjusted

        final_nominal_continuous_deg = (
            nominal_continuous_rotations[-1]
        )

        #
        # Choose the whole-turn-equivalent final rotation nearest the
        # canonical [-180, +180) region.
        #
        final_canonical_deg = (
            (
                final_nominal_continuous_deg
                + 180.0
            )
            % 360.0
        ) - 180.0

        unwind_shift_deg = (
            final_canonical_deg
            - final_nominal_continuous_deg
        )

        #
        # Snap to an exact number of full revolutions.
        #
        unwind_turns = int(
            round(
                unwind_shift_deg
                / 360.0
            )
        )

        unwind_shift_deg = (
            360.0
            * unwind_turns
        )

        if unwind_turns == 0:
            _logger.info(
                "[DROPOFF] Distributed unwind not needed: "
                "start_rotation=%.3fdeg "
                "final_nominal_continuous=%.3fdeg",
                start_rotation_deg,
                final_nominal_continuous_deg,
            )
            return adjusted

        #
        # Distribute the unwind according to cumulative XYZ travel distance.
        #
        route = [
            list(start_pose),
            *adjusted,
        ]

        segment_lengths: list[float] = []

        for index in range(
            1,
            len(route),
        ):
            previous_xyz = np.asarray(
                route[index - 1][:3],
                dtype=float,
            )

            current_xyz = np.asarray(
                route[index][:3],
                dtype=float,
            )

            segment_lengths.append(
                float(
                    np.linalg.norm(
                        current_xyz
                        - previous_xyz
                    )
                )
            )

        total_distance = float(
            sum(segment_lengths)
        )

        if total_distance <= 1e-6:
            _logger.warning(
                "[DROPOFF] Distributed unwind skipped because "
                "dropoff route has no XYZ travel"
            )
            return adjusted

        cumulative_distance = 0.0
        applied_rotations: list[float] = []

        for index, pose in enumerate(adjusted):
            cumulative_distance += (
                segment_lengths[index]
            )

            fraction = max(
                0.0,
                min(
                    1.0,
                    cumulative_distance
                    / total_distance,
                ),
            )

            nominal_continuous_deg = (
                nominal_continuous_rotations[
                    index
                ]
            )

            applied_unwind_deg = (
                unwind_shift_deg
                * fraction
            )

            final_rotation_deg = (
                nominal_continuous_deg
                + applied_unwind_deg
            )

            pose[rotation_index] = (
                final_rotation_deg
            )

            applied_rotations.append(
                final_rotation_deg
            )

        _logger.info(
            "[DROPOFF] Distributed unwind over travel: "
            "start_rotation=%.3fdeg "
            "nominal_rotations=%s "
            "unwind_turns=%d "
            "unwind_shift=%.3fdeg "
            "applied_rotations=%s "
            "travel_mm=%.3f",
            start_rotation_deg,
            [
                round(value, 3)
                for value
                in nominal_continuous_rotations
            ],
            unwind_turns,
            unwind_shift_deg,
            [
                round(value, 3)
                for value
                in applied_rotations
            ],
            total_distance,
        )

        return adjusted


    def _ordered_dropoff_preparation_segments(
        self,
    ) -> tuple[list[dict], list[float] | None]:
        """
        Build the post-paint dropoff preparation chain.

        Safe-travel/dropoff PTP poses are adjusted on the fly so the active
        rotation component progressively sheds whole-turn cable twist while
        travelling. A final standalone unwind_joint6 segment is still appended
        as a fallback in case the distributed unwind did not fully relieve J6.
        """
        config = self._paint_process_config()

        route_items: list[dict] = []

        safe_waypoints = (
            self._resolve_dropoff_safe_travel_waypoints()
        )

        if bool(
            config.dropoff_safe_travel.enabled
        ):
            if not safe_waypoints:
                return [], None

            for index, safe_waypoint in enumerate(
                safe_waypoints,
                start=1,
            ):
                route_items.append(
                    {
                        "label":
                            f"prepare_dropoff_safe_travel_{index}",

                        "position":
                            list(
                                safe_waypoint["position"]
                            ),

                        "vel":
                            float(
                                safe_waypoint[
                                    "vel_percent"
                                ]
                            ),

                        "acc":
                            float(
                                safe_waypoint[
                                    "acc_percent"
                                ]
                            ),
                    }
                )

        if self._should_prepare_dropoff_align_before_unwind():
            reference_pose = (
                route_items[-1]["position"]
                if route_items
                else self._last_process_end_pose
            )

            align_pose = (
                self._resolve_dropoff_align_pose(
                    reference_pose
                )
            )

            if align_pose is None:
                return [], None

            route_items.append(
                {
                    "label":
                        "prepare_dropoff_align",

                    "position":
                        list(align_pose),

                    "vel":
                        float(
                            config.dropoff
                            .release_align_vel_percent
                        ),

                    "acc":
                        float(
                            config.dropoff
                            .release_align_acc_percent
                        ),
                }
            )

        segments: list[dict] = []

        if route_items:
            start_pose = (
                list(self._last_process_end_pose)
                if self._last_process_end_pose is not None
                else None
            )

            adjusted_positions = (
                self._apply_distributed_dropoff_unwind(
                    [
                        item["position"]
                        for item in route_items
                    ],
                    start_pose,
                )
            )

            for index, (
                item,
                adjusted_position,
            ) in enumerate(
                zip(
                    route_items,
                    adjusted_positions,
                )
            ):
                is_last_route_pose = (
                    index
                    == len(route_items) - 1
                )

                segments.append(
                    {
                        "type": "ptp",
                        "label": item["label"],
                        "position":
                            list(adjusted_position),
                        "vel":
                            float(item["vel"]),
                        "acc":
                            float(item["acc"]),
                        "blendR": (
                            0.0
                            if is_last_route_pose
                            else 20.0
                        ),
                    }
                )

            final_pose = list(
                adjusted_positions[-1]
            )

        else:
            final_pose = (
                list(self._last_process_end_pose)
                if self._last_process_end_pose is not None
                else None
            )

        #
        # Keep the existing standalone J6 unwind as a fallback.
        #
        # The distributed unwind should normally reduce or eliminate the
        # required rotation. If J6 still needs relief, this final segment
        # completes it after the robot has reached the exact dropoff pose.
        #
        segments.append(
            {
                "type": "unwind_joint6",
                "label": "prepare_dropoff_unwind",
                "vel": float(
                    config.navigation_return
                    .unwind_vel_percent
                ),
                "acc": float(
                    config.navigation_return
                    .unwind_acc_percent
                ),
                "protected": True,
            }
        )

        return segments, final_pose

    def _try_execute_ordered_motion_cycle(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
        *,
        started: float,
    ) -> tuple[bool, str, int] | None:
        """Execute pickup, paint, optional cleanup, and pre-dropoff motion as one ordered chain."""
        execute_chain = getattr(self._robot_service, "execute_ordered_motion_chain", None)
        if not callable(execute_chain):
            return None

        pickup_plan = self._pickup.build_plan(prepared_workpiece)
        if pickup_plan is None:
            return False, "Could not compute pickup-to-pivot poses", 0
        self._last_pickup_plan = pickup_plan.motion_plan

        if pickup_plan.change_plane_combined_with_first_contact:
            with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                _logger.info(
                    "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                )

        paint_paths: list[list[list[float]]] = []
        paint_jobs: list[dict] = []
        ok, msg, total_waypoints = self._paint_contact.execute(
            prepared_workpiece,
            execute_robot=False,
            collected_command_paths=paint_paths,
            collected_command_jobs=paint_jobs,
        )
        if not ok:
            self._edge_cleanup.cancel_early_preplanning()
            return False, msg, total_waypoints
        if not paint_paths:
            return False, "Pickup succeeded, but no paint contact path was generated", total_waypoints

        segments: list[dict] = []
        for waypoint_index, waypoint in enumerate(
                pickup_plan.waypoints
        ):
            is_last_pickup_waypoint = (
                    waypoint_index
                    == len(pickup_plan.waypoints) - 1
            )

            segments.append(
                {
                    "type": "linear",
                    "label": waypoint.label,
                    "position": list(waypoint.pose),
                    "vel": float(waypoint.vel_percent),
                    "acc": float(waypoint.acc_percent),

                    #
                    # Blend all intermediate travel moves.
                    #
                    # The final one must currently stop because
                    # the following segment is type="path".
                    #
                    "blendR": (
                        0.0
                        if is_last_pickup_waypoint
                        else 20.0
                    ),
                }
            )

        for path_index, command_path in enumerate(paint_paths):
            job = paint_jobs[path_index] if path_index < len(paint_jobs) else {}
            segments.append(
                {
                    "type": "path",
                    "label": f"paint_contact_{path_index + 1}:{job.get('pattern_type', 'Path')}",
                    "path": command_path,
                    "vel": float(job.get("vel", 10.0)),
                    "acc": float(job.get("acc", 30.0)),
                    "protected": True,
                }
            )

        final_pose: list[float] | None = list(paint_paths[-1][-1])
        config = self._paint_process_config()
        if bool(config.dropoff_safe_travel.enabled) and not self._resolve_dropoff_safe_travel_positions():
            return (
                False,
                "Pivot paint finished, but paint-to-dropoff safe travel waypoints are not configured",
                total_waypoints,
            )
        if self._edge_cleanup.should_run_after_xz_ry():
            ok, msg, cleanup_waypoints, cleanup_segments, cleanup_final_pose = (
                self._edge_cleanup.build_ordered_cleanup_chain_extension(
                    prepared_workpiece,
                    started=started,
                )
            )
            total_waypoints += cleanup_waypoints
            if not ok:
                return False, msg, total_waypoints
            segments.extend(cleanup_segments)
            final_pose = cleanup_final_pose
        elif self._edge_cleanup.should_run_after_xy_rz():
            ok, msg, cleanup_waypoints, cleanup_segments, cleanup_final_pose = (
                self._edge_cleanup.build_ordered_cleanup_chain_extension(
                    prepared_workpiece,
                    started=started,
                )
            )
            total_waypoints += cleanup_waypoints
            if not ok:
                return False, msg, total_waypoints
            segments.extend(cleanup_segments)
            final_pose = cleanup_final_pose
        else:
            dropoff_segments, dropoff_final_pose = self._ordered_dropoff_preparation_segments()
            segments.extend(dropoff_segments)
            final_pose = dropoff_final_pose or final_pose

        _logger.info(
            "[ORDERED_CHAIN] executing full paint motion chain: segments=%d paint_paths=%d cleanup=%s",
            len(segments),
            len(paint_paths),
            self._edge_cleanup.should_run_after_xz_ry() or self._edge_cleanup.should_run_after_xy_rz(),
        )
        if not self._execute_ordered_segments_with_pickup_vacuum_boundary(
            "Ordered paint motion chain",
            segments,
            turn_vacuum_on=bool(pickup_plan.vacuum_on_before_moves),
        ):
            return False, "Ordered paint motion chain failed", total_waypoints

        self._dropoff_unwind_prepared = True
        if final_pose is not None:
            self._last_process_end_pose = list(final_pose)
        return True, "", total_waypoints

    @timed_step(_logger, "ordered_pickup_paint_contact_chain")
    def _try_execute_ordered_pickup_and_paint_contact(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
        *,
        control,
    ) -> tuple[bool, str, int] | None:
        """Execute pickup/staging and primary paint contact as one preplanned ordered chain."""
        execute_chain = getattr(self._robot_service, "execute_ordered_motion_chain", None)
        if not callable(execute_chain):
            return None

        pickup_plan = self._pickup.build_plan(prepared_workpiece)
        if pickup_plan is None:
            return False, "Could not compute pickup-to-pivot poses", 0
        self._last_pickup_plan = pickup_plan.motion_plan

        if pickup_plan.change_plane_combined_with_first_contact:
            with timed_block(_logger, "pickup_phase", label="Changing plane combined with first pivot contact pose"):
                _logger.info(
                    "[PICKUP] Changing plane skipped as standalone move; orientation will be combined with first pivot contact pose"
                )

        paint_paths: list[list[list[float]]] = []
        paint_jobs: list[dict] = []
        ok, msg, total_waypoints = self._paint_contact.execute(
            prepared_workpiece,
            execute_robot=False,
            collected_command_paths=paint_paths,
            collected_command_jobs=paint_jobs,
        )
        if not ok:
            self._edge_cleanup.cancel_early_preplanning()
            return False, msg, total_waypoints
        if not paint_paths:
            return False, "Pickup succeeded, but no paint contact path was generated", total_waypoints

        segments: list[dict] = []

        for waypoint_index, waypoint in enumerate(
                pickup_plan.waypoints
        ):
            is_last_pickup_waypoint = (
                    waypoint_index
                    == len(pickup_plan.waypoints) - 1
            )

            segments.append(
                {
                    "type": "linear",
                    "label": waypoint.label,
                    "position": list(waypoint.pose),
                    "vel": float(waypoint.vel_percent),
                    "acc": float(waypoint.acc_percent),

                    #
                    # Blend calibration/safe-travel/staging moves
                    # into one continuous group.
                    #
                    # The final waypoint must stop because the
                    # following segment is currently type="path".
                    #
                    "blendR": (
                        0.0
                        if is_last_pickup_waypoint
                        else 20.0
                    ),
                }
            )


        for path_index, command_path in enumerate(paint_paths):
            job = paint_jobs[path_index] if path_index < len(paint_jobs) else {}
            segments.append(
                {
                    "type": "path",
                    "label": f"paint_contact_{path_index + 1}:{job.get('pattern_type', 'Path')}",
                    "path": command_path,
                    "vel": float(job.get("vel", 10.0)),
                    "acc": float(job.get("acc", 30.0)),
                    "protected": True,
                }
            )

        dropoff_prepared_in_chain = False
        final_pose: list[float] | None = list(paint_paths[-1][-1])
        if not self._edge_cleanup.should_run_after_xz_ry() and not self._edge_cleanup.should_run_after_xy_rz():
            config = self._paint_process_config()
            if bool(config.dropoff_safe_travel.enabled) and not self._resolve_dropoff_safe_travel_positions():
                return (
                    False,
                    "Pivot paint finished, but paint-to-dropoff safe travel waypoints are not configured",
                    total_waypoints,
                )
            dropoff_segments, dropoff_final_pose = self._ordered_dropoff_preparation_segments()
            if not dropoff_segments:
                return (
                    False,
                    "Pivot paint finished, but no dropoff pose is available for safe pre-dropoff unwind alignment",
                    total_waypoints,
                )
            segments.extend(dropoff_segments)
            dropoff_prepared_in_chain = True
            final_pose = dropoff_final_pose or final_pose

        if pickup_plan.vacuum_on_before_moves:
            ok, msg = self._turn_vacuum_on()
            if not ok:
                return False, msg, total_waypoints

        active_segments = list(segments)
        chain_completed = False
        while active_segments:
            _logger.info(
                "[ORDERED_CHAIN] executing pickup plus paint contact chain: segments=%d paint_paths=%d dropoff_prep=%s",
                len(active_segments),
                len(paint_paths),
                dropoff_prepared_in_chain,
            )
            self._ordered_chain_interrupted_by_pause = False
            result = execute_chain(
                active_segments,
                tool=self._pickup_tool,
                user=self._pickup_user,
                blocking=True,
            )
            if result in (0, True, None):
                chain_completed = True
                break
            if not self._resume_after_interrupted_non_contact_motion("Ordered pickup plus paint contact chain"):
                return False, f"Ordered pickup and paint contact chain failed with code {result}", total_waypoints
            start_index = self._ordered_chain_resume_start_index
            if start_index is None:
                start_index = self._ordered_motion_chain_resume_index(self._read_ordered_motion_chain_status())
            self._ordered_chain_resume_start_index = None
            self._ordered_chain_interrupted_by_pause = False
            active_segments = active_segments[max(0, min(start_index, len(active_segments))):]
        if not chain_completed:
            return True, "", total_waypoints

        if dropoff_prepared_in_chain:
            self._dropoff_unwind_prepared = True
        if final_pose is not None:
            self._last_process_end_pose = list(final_pose)
        return True, "", total_waypoints

    def execute_paint_process(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
        *,
        control=None,
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
            previous_control = self._active_execution_control
            self._active_execution_control = control
            self._refresh_paint_process_config_snapshot()
            self._apply_paint_process_contact_config()
            self._dropoff_unwind_prepared = False
            total_waypoints = 0
            result: tuple[bool, str] = (True, "")
            contact_executed_in_ordered_chain = False

            if not self._wait_for_paint_resume(control):
                ordered_result = None
                result = (False, "Paint process stopped")
            else:
                ordered_result = (
                    self._try_execute_ordered_pickup_and_paint_contact(prepared_workpiece, control=control)
                    if control is not None
                    else self._try_execute_ordered_motion_cycle(prepared_workpiece, started=started)
                )
            if ordered_result is not None:
                ok, msg, total_waypoints = ordered_result
                result = (True, "") if ok else (False, msg)
                contact_executed_in_ordered_chain = bool(control is not None and ok)
            elif result[0]:
                # Phase 1: pickup, lift, align, change plane, and stage at first contact.
                ok, msg = self._pickup.execute(prepared_workpiece)
                if not ok:
                    _logger.info("[TIMING] paint_process success=false stage=pickup total_elapsed_s=%.3f", elapsed_s(started))
                    result = (False, msg)
                else:
                    result = (True, "")

            if ordered_result is None and result[0]:
                if not self._wait_for_paint_resume(control):
                    result = (False, "Paint process stopped")
            if (ordered_result is None or contact_executed_in_ordered_chain) and result[0]:
                with timed_block(_logger, "paint_contact_cleanup_dropoff"):
                    # Phase 2: execute the primary paint-contact path.
                    if not contact_executed_in_ordered_chain:
                        ok, msg, total_waypoints = self._paint_contact.execute(prepared_workpiece, control=control)
                        if not ok:
                            self._edge_cleanup.cancel_early_preplanning()
                            _logger.info("[TIMING] paint_process success=false stage=contact total_elapsed_s=%.3f", elapsed_s(started))
                            result = (False, msg)
                    if result[0] and not self._wait_for_paint_resume(control):
                        result = (False, "Paint process stopped")
                    if result[0] and self._edge_cleanup.should_run_after_xz_ry():
                        # Phase 3: optional edge cleanup in XY/RZ after safe cleanup unwind.
                        ok, msg, cleanup_waypoints = self._edge_cleanup.execute_after_unwind(prepared_workpiece, started)
                        total_waypoints += cleanup_waypoints
                        result = (False, msg) if not ok else (True, "")
                    elif result[0] and self._edge_cleanup.should_run_after_xy_rz():
                        # Phase 3: optional edge cleanup in XY/RZ, reprojected at the cleanup station.
                        ok, msg, cleanup_waypoints = self._edge_cleanup.execute_after_xy_rz_paint(
                            prepared_workpiece,
                            started,
                            unwind_before_cleanup=True,
                        )
                        total_waypoints += cleanup_waypoints
                        if not ok:
                            _logger.info("[TIMING] paint_process success=false stage=edge_cleanup_xy_rz total_elapsed_s=%.3f", elapsed_s(started))
                            result = (False, msg)
                        else:
                            result = (True, "")
                    elif result[0]:
                        result = (True, "")

                    if result[0] and not self._wait_for_paint_resume(control):
                        result = (False, "Paint process stopped")

                    if result[0]:
                        # Phase 4: return to safe orientation and unwind Joint 6 before dropoff.
                        ok, msg = self._prepare_dropoff_joint6_unwind()
                        if not ok:
                            _logger.info("[TIMING] paint_process success=false stage=prepare_dropoff_unwind total_elapsed_s=%.3f", elapsed_s(started))
                            result = (False, msg)

                    if result[0] and not self._wait_for_paint_resume(control):
                        result = (False, "Paint process stopped")

                    if result[0]:
                        # Phase 5: execute the configured dropoff strategy and release the part.
                        ok, msg = self._dropoff.execute(prepared_workpiece)
                        if not ok:
                            _logger.info("[TIMING] paint_process success=false stage=pre_release_dropoff total_elapsed_s=%.3f", elapsed_s(started))
                            result = (False, msg)

                    if result[0] and not self._wait_for_paint_resume(control):
                        result = (False, "Paint process stopped")

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

            if ordered_result is not None and not contact_executed_in_ordered_chain:
                if result[0]:
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
            csv_path = recorder.write_csv(self._debug_dump_dir) if self._diagnostics_artifacts_enabled() else None
            recorder.log_summary(_logger, csv_path=csv_path)
            self._active_execution_control = previous_control
            return result

    @staticmethod
    def _wait_for_paint_resume(control) -> bool:
        wait_if_paused = getattr(control, "wait_if_paused", None)
        if callable(wait_if_paused):
            return bool(wait_if_paused())
        return True

    def _diagnostics_artifacts_enabled(self) -> bool:
        config = self._paint_process_config()
        return (
            bool(getattr(config, "enable_path_debug_plots", False))
            or bool(getattr(config, "enable_pivot_debug_plot", False))
            or bool(getattr(config, "enable_execution_motion_trace", False))
        )
