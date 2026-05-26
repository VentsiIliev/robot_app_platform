from __future__ import annotations

from src.shared_contracts.events.process_events import ProcessState
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    IPaintDashboardService,
)
from src.robot_systems.paint.processes.paint.config import PaintMarkerSettings


class PaintDashboardService(IPaintDashboardService):

    def __init__(
        self,
        process,
        robot_service=None,
        navigation_service=None,
        path_executor=None,
        production_service=None,
        settings_service=None,
    ) -> None:
        self._process = process
        self._robot_service = robot_service
        self._navigation_service = navigation_service
        self._path_executor = path_executor
        self._production_service = production_service
        self._settings_service = settings_service

    def get_process_id(self) -> str:
        return str(self._process.process_id)

    def load_state(self) -> DashboardState:
        process_state = self._process.state.value
        is_paused = self._process.state == ProcessState.PAUSED
        return DashboardState(
            process_state=process_state,
            mode_label="Paint Mode",
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

    def test_pickup(self) -> tuple[bool, str]:
        if self._production_service is None:
            return False, "Production service not available"
        ok, msg = self._production_service.test_pickup()
        return ok, msg

    def go_to_calibration(self) -> None:
        if self._navigation_service is None:
            return
        self._navigation_service.move_to_calibration_position()

    def move_to_calibration_ptp(self) -> None:
        if self._navigation_service is None:
            return
        self._navigation_service.move_to_calibration_ptp()

    def move_to_home_zeros(self) -> None:
        if self._navigation_service is None:
            return
        self._navigation_service.move_to_home_all_zeros()

    def pickup_to_paint_position(self) -> tuple[bool, str]:
        if self._production_service is None:
            return False, "Production service not available"
        return self._production_service.pickup_to_paint_position()

    def test_pre_paint_marker_position(self) -> tuple[bool, str]:
        if self._production_service is None:
            return False, "Production service not available"
        return self._production_service.test_pre_paint_marker_position()

    def get_paint_marker_settings(self) -> dict:
        if self._settings_service is None:
            return PaintMarkerSettings().to_dict()
        return self._settings_service.get(CommonSettingsID.PAINT_MARKER_SETTINGS).to_dict()

    def save_paint_marker_settings(self, settings: dict) -> tuple[bool, str]:
        if self._settings_service is None:
            return False, "Settings service not available"
        try:
            marker_settings = PaintMarkerSettings.from_dict(settings or {})
            self._settings_service.save(CommonSettingsID.PAINT_MARKER_SETTINGS, marker_settings)
            return True, "Paint marker settings saved"
        except Exception as exc:
            return False, f"Failed to save paint marker settings: {exc}"

    @staticmethod
    def _active_job_label(process_state: str) -> str:
        if process_state == ProcessState.RUNNING.value:
            return "Paint job running"
        if process_state == ProcessState.PAUSED.value:
            return "Paint job paused"
        if process_state == ProcessState.STOPPED.value:
            return "Paint job stopped"
        if process_state == ProcessState.ERROR.value:
            return "Paint job error"
        return "No active job"

    @staticmethod
    def _status_lines(process_state: str) -> list[str]:
        return [
            f"Paint process state: {process_state}",
        ]
