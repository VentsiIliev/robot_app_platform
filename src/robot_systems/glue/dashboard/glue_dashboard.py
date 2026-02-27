from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import QWidget

from pl_gui.dashboard.config import CardConfig
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.glue.dashboard import config
from src.robot_systems.glue.dashboard.controller.glue_dashboard_controller import GlueDashboardController
from src.robot_systems.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_systems.glue.dashboard.service.glue_dashboard_service import GlueDashboardService
from src.robot_systems.glue.dashboard.ui.factories.glue_card_factory import GlueCardFactory
from src.robot_systems.glue.dashboard.view.glue_dashboard_view import GlueDashboardView
from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator


class GlueDashboard:

    @staticmethod
    def create(
        coordinator:       GlueOperationCoordinator,
        settings_service:  ISettingsService,
        messaging_service: IMessagingService,
        weight_service:    Optional[IWeightCellService] = None,
    ) -> QWidget:

        service = GlueDashboardService(
            runner           = coordinator,
            settings_service = settings_service,
            weight_service   = weight_service,
        )

        cells_count = service.get_cells_count()
        config.GLUE_CELLS = [
            CardConfig(card_id=i + 1, label=f"Cell {i + 1}")
            for i in range(cells_count)
        ]

        configuration = config.GlueDashboardConfig()
        model         = GlueDashboardModel(service, configuration)
        cards         = GlueCardFactory(model).build_cards(config.GLUE_CELLS)
        view          = GlueDashboardView(
            config         = config.DashboardConfig,
            action_buttons = config.ACTION_BUTTONS,
            cards          = cards,
        )
        controller = GlueDashboardController(model, view, messaging_service)
        controller.load()
        view._controller = controller
        return view