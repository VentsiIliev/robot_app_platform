from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.paint.applications.dashboard.config import (
    PAINT_DASHBOARD_ACTIONS,
    PAINT_DASHBOARD_CARDS,
    PaintDashboardConfig,
)
from src.robot_systems.paint.applications.dashboard.controller.paint_dashboard_controller import (
    PaintDashboardController,
)
from src.robot_systems.paint.applications.dashboard.model.paint_dashboard_model import (
    PaintDashboardModel,
)
from src.robot_systems.paint.applications.dashboard.service.i_paint_dashboard_service import (
    IPaintDashboardService,
)
from src.robot_systems.paint.applications.dashboard.ui.paint_card_factory import (
    PaintCardFactory,
)
from src.robot_systems.paint.applications.dashboard.view.paint_dashboard_view import (
    PaintDashboardView,
)


class PaintDashboardFactory(ApplicationFactory):
    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IPaintDashboardService) -> IApplicationModel:
        return PaintDashboardModel(service)

    def _create_view(self) -> IApplicationView:
        return PaintDashboardView(
            config=PaintDashboardConfig(),
            action_buttons=PAINT_DASHBOARD_ACTIONS,
            cards=PaintCardFactory().build_cards(PAINT_DASHBOARD_CARDS),
        )

    def _create_controller(
        self,
        model: IApplicationModel,
        view: IApplicationView,
    ) -> IApplicationController:
        return PaintDashboardController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)

