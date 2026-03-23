from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.dashboard_state import (
    DashboardState,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.service.i_my_dashboard_service import (
    IMyDashboardService,
)


class MyDashboardModel(IApplicationModel):
    def __init__(self, service: IMyDashboardService):
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
