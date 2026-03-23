from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.config import (
    MY_DASHBOARD_ACTIONS,
    MY_DASHBOARD_CARDS,
    MyDashboardConfig,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.controller.my_dashboard_controller import (
    MyDashboardController,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.model.my_dashboard_model import (
    MyDashboardModel,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.service.i_my_dashboard_service import (
    IMyDashboardService,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.ui.demo_card_factory import (
    DemoCardFactory,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.view.my_dashboard_view import (
    MyDashboardView,
)


class MyDashboardFactory(ApplicationFactory):
    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IMyDashboardService) -> IApplicationModel:
        return MyDashboardModel(service)

    def _create_view(self) -> IApplicationView:
        return MyDashboardView(
            config=MyDashboardConfig(),
            action_buttons=MY_DASHBOARD_ACTIONS,
            cards=DemoCardFactory().build_cards(MY_DASHBOARD_CARDS),
        )

    def _create_controller(
        self,
        model: IApplicationModel,
        view: IApplicationView,
    ) -> IApplicationController:
        return MyDashboardController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
