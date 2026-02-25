from __future__ import annotations

from PyQt6.QtWidgets import QWidget

from src.engine.core.message_broker import MessageBroker
from src.robot_apps.glue.dashboard.config import GlueDashboardConfig, GLUE_CELLS, ACTION_BUTTONS
from src.robot_apps.glue.dashboard.controller.glue_dashboard_controller import GlueDashboardController
from src.robot_apps.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_apps.glue.dashboard.service.i_glue_dashboard_service import IGlueDashboardService
from src.robot_apps.glue.dashboard.ui.factories.glue_card_factory import GlueCardFactory
from src.robot_apps.glue.dashboard.view.glue_dashboard_view import GlueDashboardView


class GlueDashboard:

    @staticmethod
    def create(service: IGlueDashboardService, broker: MessageBroker) -> QWidget:
        config     = GlueDashboardConfig()
        model      = GlueDashboardModel(service, config)
        cards      = GlueCardFactory(model).build_cards(GLUE_CELLS)
        view       = GlueDashboardView(config=config, action_buttons=ACTION_BUTTONS, cards=cards)
        controller = GlueDashboardController(model, view, broker)
        controller.start()
        return view
