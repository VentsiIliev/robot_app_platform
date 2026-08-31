"""Paint workpiece process executor.

This module is intentionally organized as a phase map while the executor is
still being split into smaller collaborators:

1. Runtime configuration and editor-facing API.
2. Magazine pickup/release helpers.
3. Shared pose/configuration resolvers.
4. Preview and paint-contact path projection helpers.
5. Pickup, ordered-motion, pause/resume, and vacuum helpers.
6. Dropoff preparation/unwind helpers.
7. Top-level paint process orchestration.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from src.engine.geometry.planar import (
    axis_equivalent_shift_degrees,
    rotate_xy,
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
from src.robot_systems.paint.processes.paint.execute.paint_motion_executor import PaintMotionExecutor
from src.robot_systems.paint.processes.paint.execute.pickup_executor import PaintPickupExecutor
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion import (
    project_paint_contact_motion_continuous,
    rebase_contact_motion_path_to_zero_start_rotation,
)
from src.robot_systems.paint.processes.paint.execute.projection_preview import (
    project_pivot_motion_snapshots_for_editor,
    project_pivot_paths_for_editor,
)
from src.robot_systems.paint.timing import timed_block, timed_step

_logger = logging.getLogger(__name__)

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
    z_offset_mm: float = 0.0,
    paint_axis_offset_mm: float = 0.0,
    perpendicular_axis_offset_mm: float = 0.0,
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
    perpendicular_axis_position = 1 - axis_position
    perpendicular_axis_index = pivot_config.planar_coordinate_indices[perpendicular_axis_position]
    if len(offset_pose) > perpendicular_axis_index:
        offset_pose[perpendicular_axis_index] = (
            float(offset_pose[perpendicular_axis_index]) + float(perpendicular_axis_offset_mm)
        )
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
    dryer_ready_for_release: Optional[Callable[[], tuple[bool, str]]] = None
    on_workpiece_release_verified: Optional[Callable[[], bool]] = None
    robot_config_provider: Optional[Callable[[], object]] = None
    vacuum_pump: object | None = None
    vacuum_pump_enabled_provider: Optional[Callable[[], bool]] = None
    vacuum_sensor: object | None = None
    pickup_condition: object | None = None
    pickup_condition_provider: Optional[Callable[[], object | None]] = None
    paint_process_config_service: object | None = None
    dropoff_motion_corridor_id: str | None = None

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

class _PreparedPaintProcessAdapter:
    """Minimal production-service shape for editor execution of an already prepared plan."""

    def __init__(self, path_executor: "PaintWorkpiecePathExecutor") -> None:
        self._path_executor = path_executor

    @staticmethod
    def _restore_brightness() -> None:
        return None

    @staticmethod
    def _set_dashboard_live_view_paused(_paused: bool, *, reason: str = "", image: object | None = None) -> None:
        return None

    @staticmethod
    def _log_phase_timing(_label: str, _started_at: float, **_fields: object) -> None:
        return None


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
    closed_contour_overlap_mm: float = 0.0,
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
        closed_contour_overlap_mm=max(0.0, float(closed_contour_overlap_mm)),
    )


def _xz_ry_projection_rotation_sign(motion_plane: str, mirror_execution_rotation: bool) -> float:
    """Return the planar rotation sign used during projection, before command generation."""
    if motion_plane == "xz_y_ry" and mirror_execution_rotation:
        return -1.0
    return 1.0


class PaintWorkpiecePathExecutor(IWorkpiecePathExecutor):
    """Execute prepared paint paths from pickup through paint contact and dropoff.

    The class remains the process facade. Phase-specific collaborators already
    exist for pickup, paint contact, edge cleanup, and dropoff, while this file
    still owns shared state, configuration refresh, ordered-chain assembly, and
    process-level orchestration.
    """

    supports_paint_motion_states = True
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
            dryer_ready_for_release=legacy_options.get("dryer_ready_for_release"),
            on_workpiece_release_verified=legacy_options.get(
                "on_workpiece_release_verified"
            ),
            robot_config_provider=legacy_options.get("robot_config_provider"),
            vacuum_pump=legacy_options.get("vacuum_pump"),
            vacuum_pump_enabled_provider=legacy_options.get("vacuum_pump_enabled_provider"),
            vacuum_sensor=legacy_options.get("vacuum_sensor"),
            pickup_condition=legacy_options.get("pickup_condition"),
            pickup_condition_provider=legacy_options.get("pickup_condition_provider"),
            paint_process_config_service=legacy_options.get("paint_process_config_service"),
            dropoff_motion_corridor_id=legacy_options.get("dropoff_motion_corridor_id"),
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
        self._dryer_ready_for_release = dependencies.dryer_ready_for_release
        self._on_workpiece_release_verified = dependencies.on_workpiece_release_verified
        self._robot_config_provider = dependencies.robot_config_provider
        self._vacuum_pump = dependencies.vacuum_pump
        self._vacuum_pump_enabled_provider = dependencies.vacuum_pump_enabled_provider
        self._vacuum_sensor = dependencies.vacuum_sensor
        self._pickup_condition = dependencies.pickup_condition
        self._pickup_condition_provider = dependencies.pickup_condition_provider
        self._paint_process_config_service = dependencies.paint_process_config_service
        self._dropoff_motion_corridor_id = dependencies.dropoff_motion_corridor_id

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
        self._motion = PaintMotionExecutor(self)
        self._pickup_transfer_planner = PaintPickupTransferPlanner(self)
        self._active_contact_base_z_offset_mm: float = 0.0
        self._last_process_start_rz: float | None = None
        self._last_process_end_pose: list[float] | None = None
        self._dropoff_unwind_prepared: bool = False
        self._last_pickup_contact_mode: str | None = None
        self._last_safe_travel_error: str = ""
        self._paint_process_config_snapshot: PaintProcessConfig = PAINT_PROCESS_CONFIG
        self._active_execution_control = None

    def _is_vacuum_pump_enabled(self) -> bool:
        """Return whether both process settings and live peripheral settings allow pump use."""
        if not self._enable_vacuum_pump:
            return False
        if self._vacuum_pump_enabled_provider is None:
            return True
        try:
            return bool(self._vacuum_pump_enabled_provider())
        except Exception:
            _logger.exception("[PICKUP] Failed to read live vacuum-pump enabled state")
            return False

    # -------------------------------------------------------------------------
    # Runtime Configuration And Public Editor API
    # -------------------------------------------------------------------------
    # These methods are the public surface used by the workpiece editor plus the
    # config refresh hooks needed before previewing or executing a process.

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
            closed_contour_overlap_mm=self._contact_motion_config.closed_contour_overlap_mm,
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
            if self._pickup_condition_provider is not None:
                self._pickup_condition = self._pickup_condition_provider()
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
            closed_contour_overlap_mm=config.closed_contour_overlap_mm,
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
            closed_contour_overlap_mm=self._contact_motion_config.closed_contour_overlap_mm,
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

    # -------------------------------------------------------------------------
    # Shared Pose And Settings Resolvers
    # -------------------------------------------------------------------------
    # Phase executors call back into these helpers to resolve movement-group
    # poses, configured waypoint lists, safe-travel settings, and pivot offsets.

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
    def _read_configured_waypoints(
        cls,
        positions: object,
        legacy_position: object = None,
        default_vel: float = 50.0,
        default_acc: float = 20.0,
        default_motion_type: str = "ptp",
    ) -> list[dict]:
        resolved: list[dict] = []
        if positions:
            try:
                raw_positions = list(positions)
            except TypeError:
                raw_positions = []
            for item in raw_positions:
                waypoint = cls._read_configured_waypoint(item, default_vel, default_acc, default_motion_type)
                if waypoint is not None:
                    resolved.append(waypoint)
        if resolved:
            return resolved
        legacy = cls._read_configured_waypoint(legacy_position, default_vel, default_acc, default_motion_type)
        return [legacy] if legacy is not None else []

    @classmethod
    def _read_configured_waypoint(
        cls,
        value: object,
        default_vel: float,
        default_acc: float,
        default_motion_type: str = "ptp",
    ) -> dict | None:
        pose = cls._read_configured_pose(value)
        if pose is None:
            return None
        vel = float(default_vel)
        acc = float(default_acc)
        motion_type = str(default_motion_type or "ptp").strip().lower()
        if motion_type not in {"ptp", "linear"}:
            motion_type = "ptp"
        blend_r = 0.0
        if isinstance(value, dict):
            try:
                vel = float(value.get("vel_percent", default_vel))
                acc = float(value.get("acc_percent", default_acc))
                blend_r = float(value.get("blendR", value.get("blend_r", 0.0)))
            except (TypeError, ValueError):
                vel = float(default_vel)
                acc = float(default_acc)
                blend_r = 0.0
            candidate = str(value.get("motion_type", value.get("type", "ptp")) or "ptp").strip().lower()
            if candidate in {"ptp", "linear"}:
                motion_type = candidate
        else:
            try:
                raw = list(value)
                if len(raw) >= 8:
                    vel = float(raw[6])
                    acc = float(raw[7])
                if len(raw) >= 9:
                    candidate = str(raw[8] or "ptp").strip().lower()
                    if candidate in {"ptp", "linear"}:
                        motion_type = candidate
                if len(raw) >= 10:
                    blend_r = float(raw[9])
            except (TypeError, ValueError):
                pass
        return {
            "position": pose,
            "vel_percent": vel,
            "acc_percent": acc,
            "motion_type": motion_type,
            "blendR": max(0.0, blend_r),
        }

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

    def _paint_start_staging_offset_pose(
        self,
        contact_pose: list[float],
    ) -> list[float]:
        """Return the configured plane-aware pre-contact staging pose."""
        return self._paint_staging_offset_pose(contact_pose, detach=False)

    def _paint_detach_staging_offset_pose(self, contact_pose: list[float]) -> list[float]:
        """Return the configured plane-aware post-contact staging pose."""
        return self._paint_staging_offset_pose(contact_pose, detach=True)

    def _paint_staging_offset_pose(
        self,
        contact_pose: list[float],
        *,
        detach: bool,
    ) -> list[float]:
        staging = self._paint_process_config().contact_staging
        prefix = "detach" if detach else "attach"
        return _paint_axis_staging_offset_pose(
            contact_pose,
            self._contact_motion_config,
            z_offset_mm=float(getattr(staging, f"{prefix}_z_offset_mm")),
            paint_axis_offset_mm=float(getattr(staging, f"{prefix}_paint_axis_offset_mm")),
            perpendicular_axis_offset_mm=float(
                getattr(staging, f"{prefix}_perpendicular_axis_offset_mm")
            ),
        )

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

    # -------------------------------------------------------------------------
    # Editor Preview And Paint-Contact Projection Helpers
    # -------------------------------------------------------------------------
    # These methods project prepared workpiece paths into the configured pivot
    # execution plane for editor previews and later robot command generation.

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

    # -------------------------------------------------------------------------
    # Pause / Resume Support For Ordered Non-Contact Motion
    # -------------------------------------------------------------------------
    # Paint-contact path segments are protected. Non-contact ordered motion can
    # be interrupted, then resumed from the current ordered-chain segment.

    def pause_current_execution(self) -> None:
        self._motion.pause_current_execution()

    # -------------------------------------------------------------------------
    # Paint-Contact Command Pose Helpers
    # -------------------------------------------------------------------------
    # These adapt projected paint-contact geometry into robot command poses and
    # add the retreat waypoint that moves the held part off the paint axis.

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

    def execute_paint_process(
        self,
        prepared_workpiece: WorkpieceExecutionPlan,
        *,
        control=None,
    ) -> tuple[bool, str]:
        """Run a prepared workpiece plan through the paint execution state machine."""
        from src.robot_systems.paint.processes.paint.execution_control import PaintExecutionControl
        from src.robot_systems.paint.processes.paint.execution_machine.context import PaintExecutionContext
        from src.robot_systems.paint.processes.paint.execution_machine.machine_factory import (
            PaintExecutionMachineFactory,
        )
        from src.robot_systems.paint.processes.paint.execution_machine.state import PaintExecutionState

        self._refresh_runtime_config()
        control = control or PaintExecutionControl()
        context = PaintExecutionContext(
            production_service=_PreparedPaintProcessAdapter(self),
            stop_requested=lambda: False,
            control=control,
            process_config=self._paint_process_config(),
            magazine_config=None,
        )
        context.execution_plan = prepared_workpiece

        machine = PaintExecutionMachineFactory().build(
            context,
            initial_state=PaintExecutionState.PICKUP,
        )
        machine.start_execution()
        snapshot = machine.get_snapshot()
        if snapshot.last_error is not None:
            return False, snapshot.last_error
        return context.result_ok, context.result_message

    # -------------------------------------------------------------------------
    # Process Control And Diagnostics
    # -------------------------------------------------------------------------

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
