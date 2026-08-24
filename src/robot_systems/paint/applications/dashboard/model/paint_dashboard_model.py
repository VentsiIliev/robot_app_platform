from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.paint.applications.dashboard.dashboard_state import DashboardState
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    ContourTransformDebugResult,
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

    def relieve_cable(self):
        return self._service.relieve_cable()

    def get_auxiliary_states(self) -> dict[str, bool]:
        return self._service.get_auxiliary_states()

    def set_auxiliary_enabled(self, device_id: str, enabled: bool):
        return self._service.set_auxiliary_enabled(device_id, enabled)

    def capture_latest_contour_transform_debug(self) -> ContourTransformDebugResult:
        return self._service.capture_latest_contour_transform_debug()
