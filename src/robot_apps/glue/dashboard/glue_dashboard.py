from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from pl_gui.dashboard.config import CardConfig
from src.engine.core.message_broker import MessageBroker
from src.robot_apps.glue.dashboard import config
from src.robot_apps.glue.dashboard.controller.glue_dashboard_controller import GlueDashboardController
from src.robot_apps.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_apps.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
from src.robot_apps.glue.dashboard.ui.factories.glue_card_factory import GlueCardFactory
from src.robot_apps.glue.dashboard.view.glue_dashboard_view import GlueDashboardView


class GlueDashboard:

    @staticmethod
    def create(service: IGlueDashboardService, broker: MessageBroker) -> QWidget:

        cells_count = service.get_cells_count()
        config.GLUE_CELLS  = []
        for i in range(cells_count):
            config.GLUE_CELLS.append(CardConfig(card_id= i+1,label = f"Cell {i+1}"))

        configuration     = config.GlueDashboardConfig()
        model      = GlueDashboardModel(service, configuration)
        cards      = GlueCardFactory(model).build_cards(config.GLUE_CELLS)
        try:
            view       = GlueDashboardView(config=config.DashboardConfig, action_buttons=config.ACTION_BUTTONS, cards=cards)
        except Exception as e:
            import traceback
            traceback.print_exc()
        controller = GlueDashboardController(model, view, broker)
        controller.start()
        return view
