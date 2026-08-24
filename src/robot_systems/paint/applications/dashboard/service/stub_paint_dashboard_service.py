from __future__ import annotations

from src.robot_systems.paint.applications.dashboard.dashboard_state import (
    DashboardCardState,
    DashboardState,
)
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    ContourTransformDebugResult,
    DashboardCommandResult,
    IPaintDashboardService,
)


class StubPaintDashboardService(IPaintDashboardService):
    """In-memory fake dashboard service for the standalone runner and tests.

    No hardware, robot, vision, or process wiring — every command mutates a
    local ``idle / running / paused / stopped`` state machine and ``load_state``
    renders it back into a :class:`DashboardState`.
    """

    def __init__(self, process_id: str = "paint") -> None:
        self._process_id = process_id
        self._state = "idle"
        self._auxiliary_states = {"pump": False, "fan": False}

    def get_process_id(self) -> str:
        return self._process_id

    def load_state(self) -> DashboardState:
        state = self._state
        return DashboardState(
            process_state=state,
            mode_label="Paint Mode",
            active_job_label=self._active_job_label(state),
            status_lines=self._status_lines(state),
            card_states={
                1: DashboardCardState("Robot Status", "ONLINE", "Robot service healthy"),
                2: DashboardCardState("Vision Status", "ONLINE", "Vision service healthy"),
                3: DashboardCardState("Process Status", state.upper(), self._status_lines(state)[0]),
            },
            can_start=state in ("idle", "stopped", "error"),
            can_stop=state in ("running", "paused"),
            can_pause=state in ("running", "paused"),
            pause_label="Resume" if state == "paused" else "Pause",
        )

    def start(self) -> None:
        if self._state in ("idle", "stopped", "error"):
            self._state = "running"

    def stop(self) -> None:
        if self._state in ("running", "paused"):
            self._state = "stopped"

    def pause(self) -> None:
        if self._state == "running":
            self._state = "paused"

    def resume(self) -> None:
        if self._state == "paused":
            self._state = "running"

    def reset_errors(self) -> None:
        self._state = "idle"

    def relieve_cable(self) -> DashboardCommandResult:
        return DashboardCommandResult(True, "Cable relief completed.")

    def get_auxiliary_states(self) -> dict[str, bool]:
        return dict(self._auxiliary_states)

    def set_auxiliary_enabled(self, device_id: str, enabled: bool) -> DashboardCommandResult:
        if device_id not in self._auxiliary_states:
            return DashboardCommandResult(False, f"{device_id.title()} is not available.", device_id)
        self._auxiliary_states[device_id] = enabled
        return DashboardCommandResult(True, f"{device_id.title()} switched {'ON' if enabled else 'OFF'}.", device_id, enabled)

    def capture_latest_contour_transform_debug(self) -> ContourTransformDebugResult:
        return ContourTransformDebugResult(False, "No usable contour detected (stub service).")

    @staticmethod
    def _active_job_label(state: str) -> str:
        if state == "running":
            return "Paint job running"
        if state == "paused":
            return "Paint job paused"
        if state == "stopped":
            return "Paint job stopped"
        if state == "error":
            return "Paint job error"
        return "No active job"

    @staticmethod
    def _status_lines(state: str) -> list[str]:
        if state == "running":
            return ["Painting workpiece"]
        if state == "paused":
            return ["Paint job paused"]
        if state == "stopped":
            return ["Paint job stopped"]
        if state == "error":
            return ["Resolve error before restart"]
        return ["Waiting for start"]
