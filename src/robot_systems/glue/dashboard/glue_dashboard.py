from __future__ import annotations
from typing import Callable, Optional

from PyQt6.QtWidgets import QWidget

from pl_gui.dashboard.config import CardConfig
from src.engine.system import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.robot_systems.glue.dashboard import config
from src.robot_systems.glue.dashboard.controller.glue_dashboard_controller import GlueDashboardController
from src.robot_systems.glue.dashboard.model.glue_dashboard_model import GlueDashboardModel
from src.robot_systems.glue.dashboard.service.glue_dashboard_service import GlueDashboardService
from src.robot_systems.glue.dashboard.ui.factories.glue_card_factory import GlueCardFactory
from src.robot_systems.glue.dashboard.view.glue_dashboard_view import GlueDashboardView
from src.robot_systems.glue.processes.clean_process import CleanProcess
from src.robot_systems.glue.processes.glue_operation_runner import GlueOperationRunner
from src.robot_systems.glue.processes.glue_process import GlueProcess
from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess


class GlueDashboard:

    @staticmethod
    def create(
        robot_service:     IRobotService,
        settings_service:  ISettingsService,
        messaging_service: IMessagingService,
        weight_service:    Optional[IWeightCellService]    = None,
        system_manager:    Optional[ISystemManager]        = None,
        service_checker:   Optional[Callable[[str], bool]] = None,
        requirements:      Optional[ProcessRequirements]   = None,
    ) -> QWidget:

        glue_process = GlueProcess(
            robot_service   = robot_service,
            messaging       = messaging_service,
            system_manager  = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )

        pick_and_place_process = PickAndPlaceProcess(
            robot_service   = robot_service,
            messaging       = messaging_service,
            system_manager  = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )

        clean_process = CleanProcess(
            robot_service   = robot_service,
            messaging       = messaging_service,
            system_manager  = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )

        runner = GlueOperationRunner(
            glue_process           = glue_process,
            pick_and_place_process = pick_and_place_process,
            clean_process          = clean_process,
            messaging              = messaging_service,
        )

        service = GlueDashboardService(
            runner           = runner,
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
