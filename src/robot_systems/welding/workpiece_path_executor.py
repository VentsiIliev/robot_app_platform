from __future__ import annotations

import logging

from src.applications.workpiece_editor.service.i_workpiece_path_executor import IWorkpiecePathExecutor

_logger = logging.getLogger(__name__)

class WeldingWorkpiecePathExecutor(IWorkpiecePathExecutor):
    def __init__(self, robot_service) -> None:
        self._robot_service = robot_service

    def get_supported_execution_modes(self) -> tuple[str, ...]:
        return ("continuous", "pose_path")

    def supports_pickup_to_pivot(self) -> bool:
        return False

    def get_pivot_preview_paths(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[list[list[list[float]]], list[float] | None]:
        return [], None

    def get_pivot_motion_preview(
        self,
        execution_preview_jobs: list[dict],
    ):
        return [], None

    def execute_preview_paths(
        self,
        execution_preview_jobs: list[dict],
        mode: str = "continuous",
    ) -> tuple[bool, str]:
        if not execution_preview_jobs:
            return False, "No previewed paths available to execute"
        if self._robot_service is None:
            return False, "Robot service is not available"

        mode = str(mode or "continuous").strip().lower()
        if mode not in self.get_supported_execution_modes():
            return False, f"Unsupported welding execution mode: {mode}"

        total_waypoints = 0
        for job in execution_preview_jobs:
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
                "[EXECUTE] [RUN FROM PREVIEW] Sent %d waypoints to robot in %s mode (vel=%.0f acc=%.0f)",
                len(spline), mode, vel, acc,
            )

        return True, (
            f"Executed {len(execution_preview_jobs)} path(s), "
            f"{total_waypoints} waypoints in {mode} mode"
        )

    def execute_pickup_to_pivot(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[bool, str]:
        return False, "Pickup-to-pivot is not supported in welding"

    def execute_pickup_and_pivot_paint(
        self,
        execution_preview_jobs: list[dict],
    ) -> tuple[bool, str]:
        return False, "Pickup-and-pivot-paint is not supported in welding"
