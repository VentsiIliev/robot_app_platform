from __future__ import annotations
from typing import Callable, Optional

from src.engine.application.i_application_manager import IApplicationManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.interfaces.i_robot_service import IRobotService


class PickAndPlaceProcess(BaseProcess):


    def __init__(
            self,
            robot_service: IRobotService,
            messaging: IMessagingService,
            app_manager: Optional[IApplicationManager] = None,
            requirements: Optional[ProcessRequirements] = None,
            service_checker: Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            process_id="pick_and_place",
            messaging=messaging,
            app_manager=app_manager,
            requirements=requirements,
            service_checker=service_checker,
        )
        self._robot = robot_service

    # ── BaseProcess hooks ─────────────────────────────────────────────

    def _on_start(self) -> None:
        self._logger.info("Starting pick and place process  ...")

    def _on_stop(self) -> None:
        self._logger.info("Stoping pick and place process  ...")

    def _on_pause(self) -> None:
        self._logger.info("Pausing pick and place process  ...")

    def _on_resume(self) -> None:
        self._logger.info("Resuming pick and place process  ...")

    def _on_reset_errors(self) -> None:
        self._logger.info("Reset errors in  pick and place process  ...")
        pass

