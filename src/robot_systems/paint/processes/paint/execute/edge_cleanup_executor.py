from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter

import numpy as np

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
from src.robot_systems.paint.processes.paint.execute.diagnostics import (
    elapsed_s,
    execute_paint_trajectory_with_optional_trace,
    path_length_mm,
)
from src.robot_systems.paint.timing import timed_step

_logger = logging.getLogger(__name__)

_CLEANUP_RETREAT_Y_MM = -50.0


@dataclass(frozen=True)
class _CleanupPreplan:
    ok: bool
    message: str
    total_waypoints: int
    stage_approach_pose: list[float]
    command_path: list[list[float]]


class PaintEdgeCleanupExecutor:
    """Coordinate the optional XY/RZ edge-cleanup pass after XZ/RY paint."""

    def __init__(self, owner) -> None:
        self._owner = owner
        self._active_cleanup_z_offset_mm: float | None = None
        self._last_cleanup_contact_path: list[list[float]] | None = None

    def _cleanup_speed(self) -> tuple[float, float]:
        cleanup = self._owner._paint_process_config().edge_cleanup
        return float(cleanup.vel_percent), float(cleanup.acc_percent)

    def _cleanup_config(self):
        return self._owner._paint_process_config().edge_cleanup

    def _dropoff_speed(self) -> tuple[float, float]:
        dropoff = self._owner._paint_process_config().dropoff
        return float(dropoff.release_align_vel_percent), float(dropoff.release_align_acc_percent)

    def _navigation_unwind_speed(self) -> tuple[float, float]:
        nav = self._owner._paint_process_config().navigation_return
        return float(nav.unwind_vel_percent), float(nav.unwind_acc_percent)

    def should_run_after_xz_ry(self) -> bool:
        """Return whether the configured XZ/RY process should run XY/RZ edge cleanup."""
        enabled = self._cleanup_config().enabled_after_xz_ry
        return (
            bool(enabled)
            and self._owner._configured_contact_motion_plane == "xz_y_ry"
        )

    @timed_step(_logger, "edge_cleanup_pre_unwind_align")
    def move_to_original_orientation_before_unwind(self) -> tuple[bool, str]:
        """Return the held workpiece to the saved align pose before Joint 6 unwind."""
        plan = self._owner._last_pickup_plan
        if plan is None:
            return False, "XZ/RY paint succeeded, but no pickup plan is available for safe edge-cleanup unwind alignment"
        vel, acc = self._dropoff_speed()
        if not self._owner._move_pickup_phase(
            "Returning to original orientation before edge-cleanup unwind",
            plan.align_pose,
            velocity=vel,
            acceleration=acc,
        ):
            return False, "XZ/RY paint succeeded, but return to original orientation failed before unwind"
        return True, ""

    @timed_step(_logger, "edge_cleanup_unwind")
    def unwind_joint6_before_cleanup(self, *, failure_context: str | None = None) -> tuple[bool, str]:
        """Unwind Joint 6 before the XY/RZ edge-cleanup pass."""
        if self._owner._robot_service is None:
            return False, "XZ/RY paint succeeded, but robot service is not available for Joint 6 unwind"
        vel, acc = self._navigation_unwind_speed()
        _logger.info(
            "[EDGE_CLEANUP] Unwinding Joint 6 before XY/RZ cleanup pass vel=%.1f acc=%.1f queue_if_busy=%s",
            vel,
            acc,
            PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
        )
        ok = self._owner._robot_service.unwind_joint6(
            blocking=True,
            queue_if_busy=PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
            vel=vel,
            acc=acc,
        )
        if not ok:
            if failure_context:
                return False, failure_context
            return False, "XZ/RY paint succeeded, but Joint 6 unwind failed before XY/RZ edge cleanup"
        return True, ""

    @timed_step(_logger, "edge_cleanup_stage_xy_rz")
    def stage_xy_rz_cleanup(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str]:
        """Build the XY/RZ edge-cleanup projection plan and move to its Y approach pose."""
        ok, msg, approach_pose = self._prepare_xy_rz_cleanup_stage_pose(execution_plan)
        if not ok:
            return False, msg
        vel, acc = self._cleanup_speed()
        if not self._owner._move_pickup_phase(
            "Moving to XY/RZ Y approach before edge cleanup",
            approach_pose,
            velocity=vel,
            acceleration=acc,
        ):
            return False, "XZ/RY paint succeeded, but move to XY/RZ edge-cleanup Y approach pose failed"
        return True, ""

    def _prepare_xy_rz_cleanup_stage_pose(self, execution_plan: WorkpieceExecutionPlan) -> tuple[bool, str, list[float]]:
        """Build the XY/RZ cleanup staging pose without moving the robot."""
        plan = self._owner._pickup_transfer_planner.build_plan(execution_plan)
        if plan is None:
            return False, "XZ/RY paint succeeded, but XY/RZ edge-cleanup staging could not be computed", []
        self._owner._last_pickup_plan = plan
        staged_command_pose = self._owner._paint_contact_staging_command_pose(plan.staged_pose, plan.change_plane_pose)
        cleanup_contact_pose = self._z_offset_pose(staged_command_pose)
        approach_pose = self._y_offset_pose(cleanup_contact_pose)
        return True, "", approach_pose

    @timed_step(_logger, "edge_cleanup_stage_xy_rz")
    def _move_to_preplanned_xy_rz_stage(self, approach_pose: list[float]) -> tuple[bool, str]:
        """Move to an already-computed XY/RZ edge-cleanup Y approach pose."""
        if not approach_pose:
            return False, "XZ/RY paint succeeded, but preplanned XY/RZ edge-cleanup Y approach pose is empty"
        vel, acc = self._cleanup_speed()
        if not self._owner._move_pickup_phase(
            "Moving to XY/RZ Y approach before edge cleanup",
            list(approach_pose),
            velocity=vel,
            acceleration=acc,
        ):
            return False, "XZ/RY paint succeeded, but move to XY/RZ edge-cleanup Y approach pose failed"
        return True, ""

    def _active_z_offset_mm(self) -> float:
        if self._active_cleanup_z_offset_mm is not None:
            return self._active_cleanup_z_offset_mm
        return float(self._cleanup_config().z_offset_mm)

    @staticmethod
    def _safe_float(value, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _resolve_cleanup_z_offset_mm(self, execution_plan: WorkpieceExecutionPlan) -> float:
        default = float(self._cleanup_config().z_offset_mm)
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

    def _interpolate_y_transition(
        self,
        start_pose: list[float],
        end_pose: list[float],
        *,
        include_start: bool,
        include_end: bool,
    ) -> list[list[float]]:
        """Return a Y-only transition with small steps for direct IK continuity."""
        spacing_mm = max(float(self._cleanup_config().spacing_mm), 0.5)
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

    def _wrap_contact_path_with_y_approach_and_retreat(
        self,
        command_path: list[list[float]],
        *,
        capture_contact_path: bool,
        apply_cleanup_z_offset: bool,
    ) -> list[list[float]]:
        """Return cleanup contact path wrapped with densified Y approach and retreat segments."""
        if not command_path:
            return []
        contact_path = (
            [self._z_offset_pose(pose) for pose in command_path]
            if apply_cleanup_z_offset
            else [list(pose) for pose in command_path]
        )
        if capture_contact_path:
            self._last_cleanup_contact_path = [list(pose) for pose in contact_path]
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

    def add_y_approach_and_retreat_waypoints(self, command_path: list[list[float]]) -> list[list[float]]:
        """Add densified cleanup approach and retreat segments along robot Y."""
        return self._wrap_contact_path_with_y_approach_and_retreat(
            command_path,
            capture_contact_path=True,
            apply_cleanup_z_offset=True,
        )

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
        vel, acc = self._cleanup_speed()
        if not self._owner._move_pickup_phase(
            "Retreating along Y after edge cleanup",
            retreat_pose,
            velocity=vel,
            acceleration=acc,
        ):
            return False, "XY/RZ edge cleanup succeeded, but Y retreat from cleanup contact failed"
        self._owner._last_process_end_pose = list(retreat_pose)
        return True, ""

    def _run_cleanup_pass(
        self,
        execution_plan: WorkpieceExecutionPlan,
        *,
        started: float,
        pass_name: str,
        base_z_offset_mm: float,
        execute_robot: bool = True,
    ) -> tuple[bool, str, int, list[list[float]]]:
        """Build or run one XY/RZ cleanup pass with an optional paint-axis/base Z offset."""
        cleanup_plan = execution_plan
        self._owner._active_contact_base_z_offset_mm = float(base_z_offset_mm)
        self._active_cleanup_z_offset_mm = self._resolve_cleanup_z_offset_mm(cleanup_plan)
        _logger.info(
            "[EDGE_CLEANUP] %s pass offsets resolved: base_z_offset_mm=%.3f cleanup_z_offset_mm=%.3f",
            pass_name,
            float(base_z_offset_mm),
            self._active_cleanup_z_offset_mm,
        )
        ok, msg = self.stage_xy_rz_cleanup(cleanup_plan)
        if not ok:
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_%s_stage total_elapsed_s=%.3f",
                pass_name,
                elapsed_s(started),
            )
            return False, msg, 0, []
        collected_paths: list[list[list[float]]] = []
        vel, acc = self._cleanup_speed()
        ok, msg, total_waypoints = self._owner._paint_contact.execute(
            cleanup_plan,
            vel_override=vel,
            acc_override=acc,
            append_retreat=False,
            retreat_fn=self.add_y_approach_and_retreat_waypoints,
            execute_robot=execute_robot,
            collected_command_paths=collected_paths,
        )
        command_path = [pose for path in collected_paths for pose in path]
        if not ok:
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_%s_xy_rz total_elapsed_s=%.3f",
                pass_name,
                elapsed_s(started),
            )
            return False, msg, total_waypoints, command_path
        _logger.info(
            "[EDGE_CLEANUP] XY/RZ cleanup %s pass %s: jobs=%d waypoints=%d base_z_offset_mm=%.3f",
            pass_name,
            "completed" if execute_robot else "built",
            len(cleanup_plan.execution_jobs),
            total_waypoints,
            float(base_z_offset_mm),
        )
        return True, "", total_waypoints, command_path

    def _build_cleanup_pass_path(
        self,
        execution_plan: WorkpieceExecutionPlan,
        *,
        started: float,
        pass_name: str,
        base_z_offset_mm: float,
    ) -> tuple[bool, str, int, list[list[float]], list[float]]:
        """Build one XY/RZ cleanup pass command path without moving the robot."""
        cleanup_plan = execution_plan
        self._owner._active_contact_base_z_offset_mm = float(base_z_offset_mm)
        self._active_cleanup_z_offset_mm = self._resolve_cleanup_z_offset_mm(cleanup_plan)
        _logger.info(
            "[EDGE_CLEANUP] %s preplan offsets resolved: base_z_offset_mm=%.3f cleanup_z_offset_mm=%.3f",
            pass_name,
            float(base_z_offset_mm),
            self._active_cleanup_z_offset_mm,
        )
        ok, msg, approach_pose = self._prepare_xy_rz_cleanup_stage_pose(cleanup_plan)
        if not ok:
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_%s_preplan_stage total_elapsed_s=%.3f",
                pass_name,
                elapsed_s(started),
            )
            return False, msg, 0, [], []

        collected_paths: list[list[list[float]]] = []
        vel, acc = self._cleanup_speed()
        ok, msg, total_waypoints = self._owner._paint_contact.execute(
            cleanup_plan,
            vel_override=vel,
            acc_override=acc,
            append_retreat=False,
            retreat_fn=self.add_y_approach_and_retreat_waypoints,
            execute_robot=False,
            collected_command_paths=collected_paths,
        )
        command_path = [pose for path in collected_paths for pose in path]
        if not ok:
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_%s_preplan_xy_rz total_elapsed_s=%.3f",
                pass_name,
                elapsed_s(started),
            )
            return False, msg, total_waypoints, command_path, approach_pose
        _logger.info(
            "[EDGE_CLEANUP] XY/RZ cleanup %s pass preplanned: jobs=%d waypoints=%d command_pts=%d base_z_offset_mm=%.3f",
            pass_name,
            len(cleanup_plan.execution_jobs),
            total_waypoints,
            len(command_path),
            float(base_z_offset_mm),
        )
        return True, "", total_waypoints, command_path, approach_pose

    @timed_step(_logger, "edge_cleanup_preplan_xy_rz")
    def _preplan_cleanup_path(
        self,
        execution_plan: WorkpieceExecutionPlan,
        *,
        started: float,
        combined_cleanup_enabled: bool,
    ) -> _CleanupPreplan:
        """Precompute cleanup stage and command path without robot motion."""
        preplan_started = perf_counter()
        ok, msg, total_waypoints, first_command_path, approach_pose = self._build_cleanup_pass_path(
            execution_plan,
            started=started,
            pass_name="first",
            base_z_offset_mm=0.0,
        )
        if not ok:
            return _CleanupPreplan(False, msg, total_waypoints, approach_pose, first_command_path)

        command_path = first_command_path
        if combined_cleanup_enabled:
            second_pass_z_offset = float(
                self._cleanup_config().second_pass_pivot_z_offset_mm
            )
            ok, msg, second_pass_waypoints, reverse_command_path = self._run_reverse_cleanup_pass(
                started=started,
                base_z_offset_mm=second_pass_z_offset,
                execute_robot=False,
            )
            total_waypoints += second_pass_waypoints
            if not ok:
                return _CleanupPreplan(False, msg, total_waypoints, approach_pose, first_command_path)
            command_path = first_command_path + reverse_command_path

        _logger.info(
            "[TIMING] edge_cleanup_preplan_complete success=true waypoints=%d command_pts=%d elapsed_s=%.3f",
            total_waypoints,
            len(command_path),
            elapsed_s(preplan_started),
        )
        return _CleanupPreplan(True, "", total_waypoints, approach_pose, command_path)

    @staticmethod
    def _z_offset_path(path: list[list[float]], z_offset_mm: float) -> list[list[float]]:
        """Return a copy of path shifted in robot Z."""
        shifted: list[list[float]] = []
        for source_pose in path:
            pose = list(source_pose)
            while len(pose) < 3:
                pose.append(0.0)
            pose[2] = float(pose[2]) + float(z_offset_mm)
            shifted.append(pose)
        return shifted

    def _run_reverse_cleanup_pass(
        self,
        *,
        started: float,
        base_z_offset_mm: float,
        execute_robot: bool = True,
    ) -> tuple[bool, str, int, list[list[float]]]:
        """Build or replay the first cleanup contact path backward with a shifted base Z."""
        if not self._last_cleanup_contact_path:
            return False, "XY/RZ edge cleanup first pass succeeded, but no contact path is available for reverse cleanup", 0, []

        reverse_contact_path = self._z_offset_path(
            [list(pose) for pose in reversed(self._last_cleanup_contact_path)],
            base_z_offset_mm,
        )
        command_path = self._wrap_contact_path_with_y_approach_and_retreat(
            reverse_contact_path,
            capture_contact_path=False,
            apply_cleanup_z_offset=False,
        )
        if not command_path:
            return False, "XY/RZ edge cleanup first pass succeeded, but reverse cleanup path is empty", 0, []

        _logger.info(
            "[EDGE_CLEANUP] reverse cleanup path prepared: contact_pts=%d command_pts=%d base_z_offset_mm=%.3f first_pose=%s last_pose=%s xyz_len_mm=%.3f",
            len(reverse_contact_path),
            len(command_path),
            float(base_z_offset_mm),
            [round(float(v), 3) for v in command_path[0][:6]],
            [round(float(v), 3) for v in command_path[-1][:6]],
            path_length_mm(command_path),
        )

        if not execute_robot:
            self._owner._last_process_end_pose = list(command_path[-1])
            return True, "", len(command_path), command_path

        vel, acc = self._cleanup_speed()
        if not self._owner._move_pickup_phase(
            "Moving to reverse XY/RZ cleanup Y approach",
            list(command_path[0]),
            velocity=vel,
            acceleration=acc,
        ):
            return False, "XY/RZ edge cleanup first pass succeeded, but move to reverse cleanup Y approach failed", 0, command_path

        result = execute_paint_trajectory_with_optional_trace(
            robot_service=self._owner._robot_service,
            debug_dump_dir=self._owner._debug_dump_dir,
            pivot_config=self._owner._contact_motion_config,
            command_pivot_path=command_path,
            vel=vel,
            acc=acc,
            pivot_pose=None,
            pattern_type="EdgeCleanupReverse",
            stage="edge_cleanup_reverse",
            paint_process_config=self._owner._paint_process_config(),
        )
        if result not in (0, True, None):
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_reverse_xy_rz total_elapsed_s=%.3f",
                elapsed_s(started),
            )
            return False, f"XY/RZ edge cleanup reverse pass failed with code {result}", len(command_path), command_path

        self._owner._last_process_end_pose = list(command_path[-1])
        _logger.info(
            "[EDGE_CLEANUP] reverse cleanup pass completed: waypoints=%d base_z_offset_mm=%.3f",
            len(command_path),
            float(base_z_offset_mm),
        )
        return True, "", len(command_path), command_path

    @timed_step(_logger, "edge_cleanup_combined_trajectory")
    def _execute_combined_cleanup_path(
        self,
        command_path: list[list[float]],
        *,
        started: float,
    ) -> tuple[bool, str, int]:
        """Execute the already-built combined cleanup trajectory in one robot request."""
        if not command_path:
            return False, "XY/RZ edge cleanup combined path is empty", 0
        _logger.info(
            "[EDGE_CLEANUP] executing combined cleanup trajectory: waypoints=%d xyz_len_mm=%.3f first_pose=%s last_pose=%s",
            len(command_path),
            path_length_mm(command_path),
            [round(float(v), 3) for v in command_path[0][:6]],
            [round(float(v), 3) for v in command_path[-1][:6]],
        )
        result = execute_paint_trajectory_with_optional_trace(
            robot_service=self._owner._robot_service,
            debug_dump_dir=self._owner._debug_dump_dir,
            pivot_config=self._owner._contact_motion_config,
            command_pivot_path=command_path,
            vel=self._cleanup_speed()[0],
            acc=self._cleanup_speed()[1],
            pivot_pose=None,
            pattern_type="EdgeCleanupCombined",
            stage="edge_cleanup_combined",
            paint_process_config=self._owner._paint_process_config(),
        )
        if result not in (0, True, None):
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_combined_xy_rz total_elapsed_s=%.3f",
                elapsed_s(started),
            )
            return False, f"XY/RZ edge cleanup combined trajectory failed with code {result}", len(command_path)
        self._owner._last_process_end_pose = list(command_path[-1])
        return True, "", len(command_path)

    @timed_step(_logger, "edge_cleanup_staged_trajectory")
    def _execute_staged_cleanup_path(
        self,
        stage_approach_pose: list[float],
        command_path: list[list[float]],
        *,
        started: float,
    ) -> tuple[bool, str, int]:
        """Execute stage move and preplanned cleanup trajectory in one ROS2-owned request."""
        if not command_path:
            return False, "XY/RZ edge cleanup combined path is empty", 0
        execute_staged = getattr(self._owner._robot_service, "execute_staged_trajectory", None)
        if not callable(execute_staged):
            return False, "staged trajectory endpoint unavailable", 0

        stage_vel, stage_acc = self._cleanup_speed()
        path_vel, path_acc = stage_vel, stage_acc
        _logger.info(
            "[EDGE_CLEANUP] executing staged cleanup trajectory: stage_pose=%s waypoints=%d xyz_len_mm=%.3f stage_vel=%.1f stage_acc=%.1f path_vel=%.1f path_acc=%.1f",
            [round(float(v), 3) for v in stage_approach_pose[:6]],
            len(command_path),
            path_length_mm(command_path),
            float(stage_vel),
            float(stage_acc),
            float(path_vel),
            float(path_acc),
        )
        result = execute_staged(
            stage_position=list(stage_approach_pose),
            path=command_path,
            tool=self._owner._pickup_tool,
            user=self._owner._pickup_user,
            stage_vel=stage_vel,
            stage_acc=stage_acc,
            path_vel=path_vel,
            path_acc=path_acc,
            blocking=True,
        )
        if result not in (0, True, None):
            _logger.info(
                "[TIMING] paint_process success=false stage=edge_cleanup_staged_xy_rz total_elapsed_s=%.3f",
                elapsed_s(started),
            )
            return False, f"XY/RZ edge cleanup staged trajectory failed with code {result}", len(command_path)
        self._owner._last_process_end_pose = list(command_path[-1])
        return True, "", len(command_path)

    @timed_step(_logger, "edge_cleanup_xy_rz_pass")
    def execute_after_unwind(
        self,
        execution_plan: WorkpieceExecutionPlan,
        started: float,
    ) -> tuple[bool, str, int]:
        """Run the XY/RZ edge-cleanup projection pass without releasing vacuum."""
        original_config = self._owner._contact_motion_config
        original_strategy = self._owner._contact_motion_strategy
        original_cleanup_z_offset = self._active_cleanup_z_offset_mm
        original_contact_base_z_offset = self._owner._active_contact_base_z_offset_mm
        original_cleanup_contact_path = self._last_cleanup_contact_path
        try:
            self._last_cleanup_contact_path = None
            ok, msg = self.move_to_original_orientation_before_unwind()
            if not ok:
                _logger.info("[TIMING] paint_process success=false stage=edge_cleanup_pre_unwind_align total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg, 0
            self._owner._set_runtime_contact_motion_config(self._owner._make_runtime_contact_motion_config("xy_z_rz"))
            combined_cleanup_enabled = bool(self._cleanup_config().enable_second_pass)
            wait_started = perf_counter()
            try:
                preplan = self._preplan_cleanup_path(
                    execution_plan,
                    started=started,
                    combined_cleanup_enabled=combined_cleanup_enabled,
                )
            except Exception as exc:
                _logger.exception("[EDGE_CLEANUP] preplan failed after unwind")
                return False, f"XZ/RY paint succeeded, but XY/RZ edge-cleanup preplan failed: {exc}", 0
            _logger.info(
                "[TIMING] edge_cleanup_preplan_before_unwind elapsed_s=%.3f success=%s",
                elapsed_s(wait_started),
                preplan.ok,
            )
            if not preplan.ok:
                return False, preplan.message, preplan.total_waypoints

            ok, msg = self.unwind_joint6_before_cleanup()
            if not ok:
                _logger.info("[TIMING] paint_process success=false stage=edge_cleanup_unwind total_elapsed_s=%.3f", elapsed_s(started))
                return False, msg, preplan.total_waypoints

            staged_ok, staged_msg, staged_waypoints = self._execute_staged_cleanup_path(
                preplan.stage_approach_pose,
                preplan.command_path,
                started=started,
            )
            if staged_ok:
                return True, "", staged_waypoints
            if staged_msg != "staged trajectory endpoint unavailable":
                return False, staged_msg, staged_waypoints
            _logger.warning(
                "[EDGE_CLEANUP] staged cleanup endpoint unavailable; falling back to separate stage/path execution: %s",
                staged_msg,
            )

            ok, msg = self._move_to_preplanned_xy_rz_stage(preplan.stage_approach_pose)
            if not ok:
                _logger.info(
                    "[TIMING] paint_process success=false stage=edge_cleanup_stage_xy_rz total_elapsed_s=%.3f",
                    elapsed_s(started),
                )
                return False, msg, preplan.total_waypoints

            ok, msg, combined_waypoints = self._execute_combined_cleanup_path(
                preplan.command_path,
                started=started,
            )
            if not ok:
                return False, msg, combined_waypoints
            return True, "", combined_waypoints
        finally:
            self._last_cleanup_contact_path = original_cleanup_contact_path
            self._owner._active_contact_base_z_offset_mm = original_contact_base_z_offset
            self._active_cleanup_z_offset_mm = original_cleanup_z_offset
            self._owner._contact_motion_config = original_config
            self._owner._contact_motion_strategy = original_strategy
