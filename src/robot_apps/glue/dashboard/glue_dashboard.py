from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from pl_gui.dashboard.config import CardConfig
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_apps.glue.dashboard import config
from src.robot_apps.glue.dashboard.controller.glue_dashboard_controller import GlueDashboardController
from src.robot_apps.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_apps.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
from src.robot_apps.glue.dashboard.ui.factories.glue_card_factory import GlueCardFactory
from src.robot_apps.glue.dashboard.view.glue_dashboard_view import GlueDashboardView


class GlueDashboard:

    @staticmethod
    def create(service: IGlueDashboardService, messaging_service: IMessagingService) -> QWidget:

        cells_count = service.get_cells_count()
        config.GLUE_CELLS  = []
        for i in range(cells_count):
            config.GLUE_CELLS.append(CardConfig(card_id= i+1,label = f"Cell {i+1}"))

        configuration     = config.GlueDashboardConfig()
        model      = GlueDashboardModel(service, configuration)
        cards      = GlueCardFactory(model).build_cards(config.GLUE_CELLS)

        view       = GlueDashboardView(config=config.DashboardConfig, action_buttons=config.ACTION_BUTTONS, cards=cards)

        controller = GlueDashboardController(model, view, messaging_service)
        controller.load()
        view._controller = controller  # explicit ownership — do not rely on _subs lambdas
        return view
