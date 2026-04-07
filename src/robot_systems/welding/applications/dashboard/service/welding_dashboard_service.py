from __future__ import annotations

from src.shared_contracts.events.process_events import ProcessState
from src.robot_systems.welding.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.welding.applications.dashboard.service.i_welding_dashboard_service import (
    IWeldingDashboardService,
)


class WeldingDashboardService(IWeldingDashboardService):

    def __init__(self, process) -> None:
        self._process = process

    def get_process_id(self) -> str:
        return str(self._process.process_id)

    def load_state(self) -> DashboardState:
        process_state = self._process.state.value
        is_paused = self._process.state == ProcessState.PAUSED
        return DashboardState(
            process_state=process_state,
            mode_label="Welding Mode",
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
            return "Welding job running"
        if process_state == ProcessState.PAUSED.value:
            return "Welding job paused"
        if process_state == ProcessState.STOPPED.value:
            return "Welding job stopped"
        if process_state == ProcessState.ERROR.value:
            return "Welding job error"
        return "No active job"

    @staticmethod
    def _status_lines(process_state: str) -> list[str]:
        return [
            f"Welding process state: {process_state}",
        ]

