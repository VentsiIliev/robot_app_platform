from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.twin_robot.applications.dashboard.controller.twin_dashboard_controller import (
    TwinDashboardController,
)
from src.robot_systems.twin_robot.applications.dashboard.model.twin_dashboard_model import (
    TwinDashboardModel,
)
from src.robot_systems.twin_robot.applications.dashboard.service.i_twin_dashboard_service import (
    ITwinDashboardService,
)
from src.robot_systems.twin_robot.applications.dashboard.view.twin_dashboard_view import (
    TwinDashboardView,
)


class TwinDashboardFactory(ApplicationFactory):
    def _create_model(self, service: ITwinDashboardService) -> IApplicationModel:
        return TwinDashboardModel(service)

    def _create_view(self) -> IApplicationView:
        return TwinDashboardView()

    def _create_controller(
        self,
        model: IApplicationModel,
        view: IApplicationView,
    ) -> IApplicationController:
        return TwinDashboardController(model, view)
