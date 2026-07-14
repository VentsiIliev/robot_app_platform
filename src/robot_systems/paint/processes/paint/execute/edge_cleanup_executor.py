from __future__ import annotations

import logging

import numpy as np

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
from src.robot_systems.paint.processes.paint.execute.diagnostics import elapsed_s
from src.robot_systems.paint.timing import timed_step

_logger = logging.getLogger(__name__)

_CLEANUP_RETREAT_Y_MM = -50.0


class PaintEdgeCleanupExecutor:
    """Coordinate the optional XY/RZ edge-cleanup pass after XZ/RY paint."""

    def __init__(self, owner) -> None:
        self._owner = owner
        self._active_cleanup_z_offset_mm: float | None = None

    def should_run_after_xz_ry(self) -> bool:
        """Return whether the configured XZ/RY process should run XY/RZ edge cleanup."""
        enabled = getattr(PAINT_PROCESS_CONFIG, "enable_edge_cleanup_after_xz_ry", False)
        return (
            bool(enabled)
            and self._owner._configured_pivot_motion_plane == "xz_y_ry"
        )

    @timed_step(_logger, "edge_cleanup_pre_unwind_align")
    def move_to_original_orientation_before_unwind(self) -> tuple[bool, str]:
        """Return the held workpiece to the saved align pose before Joint 6 unwind."""
        plan = self._owner._last_pickup_plan
        if plan is None:
            return False, "XZ/RY paint succeeded, but no pickup plan is available for safe edge-cleanup unwind alignment"
        ok, msg = self._validate_current_to_pose(plan.align_pose, "pre-unwind original orientation")
        if not ok:
            return False, msg
        if not self._owner._move_pickup_phase(
            "Returning to original orientation before edge-cleanup unwind",
            plan.align_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_release_align_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_release_align_acc_percent,
        ):
            return False, "XZ/RY paint succeeded, but return to original orientation failed before unwind"
        return True, ""

    @timed_step(_logger, "edge_cleanup_unwind")
    def unwind_joint6_before_cleanup(self) -> tuple[bool, str]:
        """Unwind Joint 6 before the XY/RZ edge-cleanup pass."""
        if self._owner._robot_service is None:
            return False, "XZ/RY paint succeeded, but robot service is not available for Joint 6 unwind"
        _logger.info(
            "[EDGE_CLEANUP] Unwinding Joint 6 before XY/RZ cleanup pass vel=%.1f acc=%.1f queue_if_busy=%s",
            PAINT_PROCESS_CONFIG.navigation_unwind_vel_percent,
            PAINT_PROCESS_CONFIG.navigation_unwind_acc_percent,
            PAINT_PROCESS_CONFIG.navigation_unwind_queue_if_busy,
        )
        ok = self._owner._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=PAINT_PROCESS_CONFIG.navigation_unwind_queue_if_busy,
            vel=PAINT_PROCESS_CONFIG.navigation_unwind_vel_percent,
            acc=PAINT_PROCESS_CONFIG.navigation_unwind_acc_percent,
        )
        if not ok:
            return False, "XZ/RY paint succeeded, but Joint 6 unwind failed before XY/RZ edge cleanup"
        return True, ""

    def _validate_current_to_pose(self, pose: list[float], label: str) -> tuple[bool, str]:
        """Validate a direct transition from the current robot pose when supported."""
        if not PAINT_PROCESS_CONFIG.pickup_edge_cleanup_validate_transition_poses:
            return True, ""
        if self._owner._robot_service is None:
            return True, ""
        try:
            current = self._owner._robot_service.get_current_position()
        except Exception:
            _logger.debug("[EDGE_CLEANUP] Could not read current pose before %s", label, exc_info=True)
            return True, ""
        if not current or len(current) < 3:
            return True, ""
        try:
            result = self._owner._robot_service.validate_pose(
                list(current),
                list(pose),
                tool=self._owner._pickup_tool,
                user=self._owner._pickup_user,
            )
        except Exception:
            _logger.debug("[EDGE_CLEANUP] Pose validation failed before %s", label, exc_info=True)
            return True, ""
        if result.get("supported") is False:
            return True, ""
        if bool(result.get("reachable", True)):
            return True, ""
        reason = str(result.get("reason") or result.get("error") or "unreachable")
        return False, f"XZ/RY paint succeeded, but {label} is unreachable ({reason})"

    @timed_step(_logger, "edge_cleanup_stage_xy_rz")
    def stage_xy_rz_cleanup(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str]:
        """Build the XY/RZ edge-cleanup projection plan and move to its Y approach pose."""
        plan = self._owner._build_pickup_and_stage_poses(execution_plan)
        if plan is None:
            return False, "XZ/RY paint succeeded, but XY/RZ edge-cleanup staging could not be computed"
        self._owner._last_pickup_plan = plan
        staged_command_pose = self._owner._pivot_staging_command_pose(plan.staged_pose, plan.change_plane_pose)
        cleanup_contact_pose = self._z_offset_pose(staged_command_pose)
        approach_pose = self._y_offset_pose(cleanup_contact_pose)
        ok, msg = self._validate_current_to_pose(approach_pose, "XY/RZ edge-cleanup Y approach")
        if not ok:
            return False, msg
        if not self._owner._move_pickup_phase(
            "Moving to XY/RZ Y approach before edge cleanup",
            approach_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_edge_cleanup_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_edge_cleanup_acc_percent,
        ):
            return False, "XZ/RY paint succeeded, but move to XY/RZ edge-cleanup Y approach pose failed"
        return True, ""

    def _active_z_offset_mm(self) -> float:
        if self._active_cleanup_z_offset_mm is not None:
            return self._active_cleanup_z_offset_mm
        return float(PAINT_PROCESS_CONFIG.pickup_edge_cleanup_z_offset_mm)

    @staticmethod
    def _safe_float(value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _resolve_cleanup_z_offset_mm(self, execution_plan: WorkpieceExecutionPlan) -> float:
        default = float(PAINT_PROCESS_CONFIG.pickup_edge_cleanup_z_offset_mm)
        jobs = list(getattr(execution_plan, "execution_jobs", []) or [])
        for job in jobs:
            if not isinstance(job, dict):
                continue
            if job.get("edge_cleanup_z_offset_mm") is not None:
                return self._safe_float(job.get("edge_cleanup_z_offset_mm"), default)
            settings = job.get("settings")
            if isinstance(settings, dict) and settings.get("edge_cleanup_z_offset_mm") is not None:
                return self._safe_float(settings.get("edge_cleanup_z_offset_mm"), default)
        workpiece = getattr(execution_plan, "workpiece", {}) or {}
        if isinstance(workpiece, dict):
            if workpiece.get("edge_cleanup_z_offset_mm") is not None:
                return self._safe_float(workpiece.get("edge_cleanup_z_offset_mm"), default)
            settings = workpiece.get("settings")
            if isinstance(settings, dict) and settings.get("edge_cleanup_z_offset_mm") is not None:
                return self._safe_float(settings.get("edge_cleanup_z_offset_mm"), default)
        return default

    def _z_offset_pose(self, contact_pose: list[float]) -> list[float]:
        """Return the cleanup contact pose with the configured Z press offset applied."""
        pose = list(contact_pose)
        while len(pose) < 3:
            pose.append(0.0)
        pose[2] = float(pose[2]) + self._active_z_offset_mm()
        return pose

    @staticmethod
    def _y_offset_pose(contact_pose: list[float]) -> list[float]:
        """Return the cleanup Y-offset pose used for both approach and retreat."""
        retreat_pose = list(contact_pose)
        while len(retreat_pose) < 3:
            retreat_pose.append(0.0)
        retreat_pose[1] = float(retreat_pose[1]) + _CLEANUP_RETREAT_Y_MM
        return retreat_pose

    @staticmethod
    def _interpolate_y_transition(
        start_pose: list[float],
        end_pose: list[float],
        *,
        include_start: bool,
        include_end: bool,
    ) -> list[list[float]]:
        """Return a Y-only transition with small steps for direct IK continuity."""
        spacing_mm = max(float(PAINT_PROCESS_CONFIG.pickup_edge_cleanup_spacing_mm), 0.5)
        start = list(start_pose)
        end = list(end_pose)
        while len(start) < 6:
            start.append(0.0)
        while len(end) < 6:
            end.append(0.0)
        delta_y = float(end[1]) - float(start[1])
        steps = max(int(np.ceil(abs(delta_y) / spacing_mm)), 1)
        first_step = 0 if include_start else 1
        last_step = steps if include_end else steps - 1
        transition: list[list[float]] = []
        for step in range(first_step, last_step + 1):
            t = float(step) / float(steps)
            pose = list(end)
            pose[1] = float(start[1]) + delta_y * t
            transition.append(pose)
        return transition

    def add_y_approach_and_retreat_waypoints(self, command_path: list[list[float]]) -> list[list[float]]:
        """Add densified cleanup approach and retreat segments along robot Y."""
        if not command_path:
            return []
        contact_path = [self._z_offset_pose(pose) for pose in command_path]
        first_contact_pose = list(contact_path[0])
        final_contact_pose = list(contact_path[-1])
        approach_pose = self._y_offset_pose(first_contact_pose)
        retreat_pose = self._y_offset_pose(final_contact_pose)
        approach_segment = self._interpolate_y_transition(
            approach_pose,
            first_contact_pose,
            include_start=True,
            include_end=False,
        )
        retreat_segment = self._interpolate_y_transition(
            final_contact_pose,
            retreat_pose,
            include_start=False,
            include_end=True,
        )
        _logger.info(
            "[EDGE_CLEANUP] added Y approach/retreat segments: approach_pts=%d retreat_pts=%d z_offset_mm=%.3f approach_pose=%s first_contact=%s final_contact=%s retreat_pose=%s",
            len(approach_segment),
            len(retreat_segment),
            self._active_z_offset_mm(),
            [round(float(v), 3) for v in approach_pose[:6]],
            [round(float(v), 3) for v in first_contact_pose[:6]],
            [round(float(v), 3) for v in final_contact_pose[:6]],
            [round(float(v), 3) for v in retreat_pose[:6]],
        )
        return approach_segment + contact_path + retreat_segment

    def append_y_retreat_waypoint(self, command_path: list[list[float]]) -> list[list[float]]:
        """Append a cleanup-only retreat waypoint along robot Y."""
        if not command_path:
            return []
        path_with_retreat = [list(pose) for pose in command_path]
        final_contact_pose = list(path_with_retreat[-1])
        retreat_pose = self._y_offset_pose(final_contact_pose)
        if np.allclose(
            np.asarray(final_contact_pose[:3], dtype=float),
            np.asarray(retreat_pose[:3], dtype=float),
            atol=1e-6,
        ):
            return path_with_retreat
        path_with_retreat.append(retreat_pose)
        _logger.info(
            "[EDGE_CLEANUP] appended Y retreat waypoint: contact_pose=%s retreat_pose=%s",
            [round(float(v), 3) for v in final_contact_pose[:6]],
            [round(float(v), 3) for v in retreat_pose[:6]],
        )
        return path_with_retreat

    @timed_step(_logger, "edge_cleanup_y_retreat")
    def move_y_retreat_after_cleanup(self) -> tuple[bool, str]:
        """Move off the cleanup contact path along robot Y after contour execution."""
        final_contact_pose = self._owner._last_process_end_pose
        if not final_contact_pose:
            return False, "XY/RZ edge cleanup succeeded, but no final contact pose is available for Y retreat"
        retreat_path = self.append_y_retreat_waypoint([list(final_contact_pose)])
        if len(retreat_path) < 2:
            return True, ""
        retreat_pose = retreat_path[-1]
        ok, msg = self._validate_current_to_pose(retreat_pose, "XY/RZ edge-cleanup Y retreat")
        if not ok:
            return False, msg
        if not self._owner._move_pickup_phase(
            "Retreating along Y after edge cleanup",
            retreat_pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_edge_cleanup_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_edge_cleanup_acc_percent,
        ):
            return False, "XY/RZ edge cleanup succeeded, but Y retreat from cleanup contact failed"
        self._owner._last_process_end_pose = list(retreat_pose)
        return True, ""

    @timed_step(_logger, "edge_cleanup_xy_rz_pass")
    def execute_after_unwind(
        self,
        execution_plan: WorkpieceExecutionPlan,
        started: float,
    ) -> tuple[bool, str, int]:
        """Run the XY/RZ edge-cleanup projection pass without releasing vacuum."""
        original_config = self._owner._pivot_config
        original_strategy = self._owner._pivot_strategy
        original_cleanup_z_offset = self._active_cleanup_z_offset_mm
        try:
            ok, msg = self.move_to_original_orientation_before_unwind()
            if not ok:
                _logger.info("[TIMING] pickup_and_paint success=false stage=edge_cleanup_pre_unwind_align total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg, 0
            ok, msg = self.unwind_joint6_before_cleanup()
            if not ok:
                _logger.info("[TIMING] pickup_and_paint success=false stage=edge_cleanup_unwind total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg, 0
            self._owner._set_runtime_pivot_config(self._owner._make_runtime_pivot_config("xy_z_rz"))
            cleanup_plan = execution_plan
            self._active_cleanup_z_offset_mm = self._resolve_cleanup_z_offset_mm(cleanup_plan)
            _logger.info(
                "[EDGE_CLEANUP] cleanup z offset resolved: %.3f mm",
                self._active_cleanup_z_offset_mm,
            )
            ok, msg = self.stage_xy_rz_cleanup(cleanup_plan)
            if not ok:
                _logger.info("[TIMING] pickup_and_paint success=false stage=edge_cleanup_stage total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg, 0
            ok, msg, total_waypoints = self._owner._execute_pivot_paths(
                cleanup_plan,
                vel_override=PAINT_PROCESS_CONFIG.pickup_edge_cleanup_vel_percent,
                acc_override=PAINT_PROCESS_CONFIG.pickup_edge_cleanup_acc_percent,
                append_retreat=False,
                retreat_fn=self.add_y_approach_and_retreat_waypoints,
            )
            if not ok:
                _logger.info("[TIMING] pickup_and_paint success=false stage=edge_cleanup_xy_rz total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg, total_waypoints
            _logger.info(
                "[EDGE_CLEANUP] XY/RZ cleanup pass completed: jobs=%d waypoints=%d",
                len(cleanup_plan.execution_jobs),
                total_waypoints,
            )
            return True, "", total_waypoints
        finally:
            self._active_cleanup_z_offset_mm = original_cleanup_z_offset
            self._owner._pivot_config = original_config
            self._owner._pivot_strategy = original_strategy
