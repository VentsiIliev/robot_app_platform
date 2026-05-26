from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    IPaintDashboardService,
)


class PaintDashboardModel(IApplicationModel):
    def __init__(self, service: IPaintDashboardService):
        self._service = service

    def load(self) -> DashboardState:
        return self._service.load_state()

    def save(self, _data) -> None:
        return None

    def start(self) -> DashboardState:
        self._service.start()
        return self.load()

    def stop_process(self) -> DashboardState:
        self._service.stop()
        return self.load()

    def toggle_pause(self) -> DashboardState:
        state = self.load()
        if state.process_state == "paused":
            self._service.resume()
        else:
            self._service.pause()
        return self.load()

    def reset_errors(self) -> DashboardState:
        self._service.reset_errors()
        return self.load()

    def test_pickup(self) -> None:
        self._service.test_pickup()

    def go_to_calibration(self) -> None:
        self._service.go_to_calibration()

    def move_to_calibration_ptp(self) -> None:
        self._service.move_to_calibration_ptp()

    def move_to_home_zeros(self) -> None:
        self._service.move_to_home_zeros()

    def pickup_to_paint_position(self) -> None:
        self._service.pickup_to_paint_position()

    def test_pre_paint_marker_position(self) -> tuple[bool, str]:
        return self._service.test_pre_paint_marker_position()

    def get_paint_marker_settings(self) -> dict:
        return self._service.get_paint_marker_settings()

    def save_paint_marker_settings(self, settings: dict) -> tuple[bool, str]:
        return self._service.save_paint_marker_settings(settings)
