from __future__ import annotations

from src.shared_contracts.events.process_events import ProcessState
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.dashboard_state import (
    DashboardState,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.service.i_my_dashboard_service import (
    IMyDashboardService,
)


class DemoMyDashboardService(IMyDashboardService):
    """
    Runnable blueprint dashboard service.

    TODO: Replace this with a service backed by your real coordinator/process.
    Recommended replacement order:
    1. inject your coordinator or main process
    2. map process states into DashboardState
    3. delegate start/stop/pause/resume to the coordinator
    4. expose any system-specific status lines from settings/services
    5. publish/subscribe live updates through the broker if needed
    """

    def __init__(self, process) -> None:
        self._process = process

    def get_process_id(self) -> str:
        return str(self._process.process_id)

    def load_state(self) -> DashboardState:
        process_state = self._process.state.value
        is_paused = self._process.state == ProcessState.PAUSED
        return DashboardState(
            process_state=process_state,
            mode_label="Demo Mode",
            active_job_label=self._active_job_label(process_state),
            status_lines=self._status_lines(process_state),
            can_start=process_state in (ProcessState.IDLE.value, ProcessState.STOPPED.value),
            can_stop=process_state in (ProcessState.RUNNING.value, ProcessState.PAUSED.value),
            can_pause=process_state in (ProcessState.RUNNING.value, ProcessState.PAUSED.value),
            pause_label="Resume" if is_paused else "Pause",
        )

    def start(self) -> None:
        self._process.start()

    def stop(self) -> None:
        self._process.stop()

    def pause(self) -> None:
        self._process.pause()

    def resume(self) -> None:
        self._process.resume()

    def reset_errors(self) -> None:
        self._process.reset_errors()

    @staticmethod
    def _active_job_label(process_state: str) -> str:
        if process_state == ProcessState.RUNNING.value:
            return "Demo job running"
        if process_state == ProcessState.PAUSED.value:
            return "Demo job paused"
        if process_state == ProcessState.STOPPED.value:
            return "Demo job stopped"
        if process_state == ProcessState.ERROR.value:
            return "Demo job error"
        return "No active job"

    @staticmethod
    def _status_lines(process_state: str) -> list[str]:
        return [
            f"Blueprint process state: {process_state}",
            "TODO: Replace DemoProcess with your real coordinator-backed process.",
            "TODO: Map richer job/progress/health state into DashboardState.",
        ]
