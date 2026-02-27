from __future__ import annotations
from typing import Callable, Optional

from src.engine.system import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.interfaces.i_robot_service import IRobotService


class GlueProcess(BaseProcess):
    """
    The gluing process — owns the robot lifecycle for the glue dispensing operation.
    Lives in robot_systems/glue/processes/ — all system-specific processes live here.
    """

    def __init__(
        self,
        robot_service:   IRobotService,
        messaging:       IMessagingService,
        system_manager:     Optional[ISystemManager]   = None,
        requirements:    Optional[ProcessRequirements]   = None,
        service_checker: Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            process_id      = "glue",
            messaging       = messaging,
            system_manager     = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )
        self._robot = robot_service

    # ── BaseProcess hooks ─────────────────────────────────────────────

    def _on_start(self) -> None:
        self._robot.enable_robot()

    def _on_stop(self) -> None:
        self._robot.stop_motion()
        self._robot.disable_robot()

    def _on_pause(self) -> None:
        self._robot.stop_motion()

    def _on_resume(self) -> None:
        self._robot.enable_robot()

    def _on_reset_errors(self) -> None:
        pass

