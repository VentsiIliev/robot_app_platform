from __future__ import annotations

import logging

from src.applications.workpiece_editor.service.i_workpiece_path_executor import (
    IWorkpiecePathExecutor,
    WorkpieceProcessAction,
)
from src.engine.robot.path_preparation import WorkpieceExecutionPlan

_logger = logging.getLogger(__name__)

class WeldingWorkpiecePathExecutor(IWorkpiecePathExecutor):
    def __init__(self, robot_service) -> None:
        self._robot_service = robot_service

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        return ("continuous", "pose_path")

    def get_process_actions(self) -> tuple[WorkpieceProcessAction, ...]:
        return (
            WorkpieceProcessAction(
                action_id="weld_continuous",
                label="Run Weld Continuous",
            ),
            WorkpieceProcessAction(
                action_id="weld_pose_path",
                label="Run Weld Pose Path",
            ),
        )

    def execute_process_action(
        self,
        execution_plan: WorkpieceExecutionPlan,
        action_id: str,
    ) -> tuple[bool, str]:
        action_id = str(action_id or "").strip().lower()
        if action_id == "weld_continuous":
            return self.execute_preview_paths(execution_plan, mode="continuous")
        if action_id == "weld_pose_path":
            return self.execute_preview_paths(execution_plan, mode="pose_path")
        return False, f"Unsupported welding process action: {action_id}"

    def supports_pickup_to_pivot(self) -> bool:
        return False

    def get_pivot_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        return [], None

    def get_pivot_motion_preview(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ):
        return [], None

    def execute_preview_paths(
        self,
        execution_plan: WorkpieceExecutionPlan,
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        jobs = execution_plan.execution_jobs
        if not jobs:
            return False, "No prepared process paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        mode = str(mode or "continuous").strip().lower()
        if mode not in self.get_supported_execution_modes():
            return False, f"Unsupported welding execution mode: {mode}"

        total_waypoints = 0
        for job in jobs:
            spline = job.get("execution_path") or job.get("path") or []
            vel = float(job.get("vel", 60.0))
            acc = float(job.get("acc", 30.0))
            pattern_type = str(job.get("pattern_type", "Path"))
            if not spline:
                continue

            orientation_mode = "per_waypoint" if mode == "pose_path" else "constant"
            _logger.debug(f"Mode {mode} selected, using orientation mode: {orientation_mode}")
            result = self._robot_service.execute_trajectory(
                spline,
                vel=vel,
                acc=acc,
                blocking=True,
                orientation_mode=orientation_mode,
            )
            if result not in (0, True, None):
                return False, f"{pattern_type} {mode} execution failed with code {result}"

            total_waypoints += len(spline)
            _logger.info(
                "[EXECUTE] [RUN PROCESS] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
                len(spline), mode, vel, acc,
            )

        return True, (
            f"Executed {len(jobs)} path(s), "
            f"{total_waypoints} waypoints in {mode} mode"
        )

    def execute_pickup_to_pivot(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        return False, "Pickup-to-pivot is not supported in welding"

    def execute_pickup_and_paint(
        self,
        execution_plan: WorkpieceExecutionPlan,
    ) -> tuple[bool, str]:
        return False, "Pickup-and-pivot-paint is not supported in welding"
