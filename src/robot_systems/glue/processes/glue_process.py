from __future__ import annotations
from typing import Callable, Optional

from src.robot_systems.glue.navigation import GlueNavigationService
from src.robot_systems.glue.process_ids import ProcessID
from src.engine.system import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.interfaces.i_robot_service import IRobotService


class GlueProcess(BaseProcess):
    """
    The gluing process — owns the robot lifecycle for the glue dispensing operation.
    Lives in robot_systems/glue/processes/ — all vision_service-specific processes live here.
    """

    def __init__(
        self,
        robot_service:   IRobotService,
        navigation_service: GlueNavigationService,
        messaging:       IMessagingService,
        system_manager:     Optional[ISystemManager]   = None,
        requirements:    Optional[ProcessRequirements]   = None,
        service_checker: Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            process_id      = ProcessID.GLUE,
            messaging       = messaging,
            system_manager     = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )
        self._robot = robot_service
        self.navigation_service = navigation_service

    # ── BaseProcess hooks ─────────────────────────────────────────────

    def _on_start(self) -> None:
        # self._robot.enable_robot()
        # self.navigation_service.move_to_calibration_position()
        self._logger.info("Glue started")

    def _on_stop(self) -> None:
        # self._robot.stop_motion()
        # self._robot.disable_robot()
        self._logger.info("Glue stopped")

    def _on_pause(self) -> None:
        # self._robot.stop_motion()
        self._logger.info("Glue paused")

    def _on_resume(self) -> None:
        # self._robot.enable_robot()
        self._logger.info("Glue resumed")

    def _on_reset_errors(self) -> None:
        self._logger.info("Glue errors reset")

