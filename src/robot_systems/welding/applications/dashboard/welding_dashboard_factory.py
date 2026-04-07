from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.welding.applications.dashboard.config import (
    WELDING_DASHBOARD_ACTIONS,
    WELDING_DASHBOARD_CARDS,
    WeldingDashboardConfig,
)
from src.robot_systems.welding.applications.dashboard.controller.welding_dashboard_controller import (
    WeldingDashboardController,
)
from src.robot_systems.welding.applications.dashboard.model.welding_dashboard_model import (
    WeldingDashboardModel,
)
from src.robot_systems.welding.applications.dashboard.service.i_welding_dashboard_service import (
    IWeldingDashboardService,
)
from src.robot_systems.welding.applications.dashboard.ui.welding_card_factory import (
    WeldingCardFactory,
)
from src.robot_systems.welding.applications.dashboard.view.welding_dashboard_view import (
    WeldingDashboardView,
)


class WeldingDashboardFactory(ApplicationFactory):
    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IWeldingDashboardService) -> IApplicationModel:
        return WeldingDashboardModel(service)

    def _create_view(self) -> IApplicationView:
        return WeldingDashboardView(
            config=WeldingDashboardConfig(),
            action_buttons=WELDING_DASHBOARD_ACTIONS,
            cards=WeldingCardFactory().build_cards(WELDING_DASHBOARD_CARDS),
        )

    def _create_controller(
        self,
        model: IApplicationModel,
        view: IApplicationView,
    ) -> IApplicationController:
        return WeldingDashboardController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)

