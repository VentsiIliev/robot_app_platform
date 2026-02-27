from __future__ import annotations
import threading
from typing import Callable, Optional

from src.engine.system.i_system_manager import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.interfaces.i_robot_service import IRobotService

_SIMULATION_DURATION_S = 3.0


class PickAndPlaceProcess(BaseProcess):

    def __init__(
            self,
            robot_service:   IRobotService,
            messaging:       IMessagingService,
            system_manager:  Optional[ISystemManager]        = None,
            requirements:    Optional[ProcessRequirements]   = None,
            service_checker: Optional[Callable[[str], bool]] = None,
            simulation_duration_s: float = _SIMULATION_DURATION_S,
    ):
        super().__init__(
            process_id      = "pick_and_place",
            messaging       = messaging,
            system_manager  = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )
        self._robot              = robot_service
        self._simulation_duration = simulation_duration_s
        self._sim_timer: Optional[threading.Timer] = None

    # ── BaseProcess hooks ─────────────────────────────────────────────

    def _on_start(self) -> None:
        self._logger.info("Pick-and-place started — simulating %.1fs of work", self._simulation_duration)
        self._sim_timer = threading.Timer(self._simulation_duration, self._simulation_complete)
        self._sim_timer.daemon = True
        self._sim_timer.start()

    def _on_stop(self) -> None:
        self._cancel_timer()
        self._logger.info("Pick-and-place stopped")

    def _on_pause(self) -> None:
        self._cancel_timer()
        self._logger.info("Pick-and-place paused")

    def _on_resume(self) -> None:
        self._logger.info("Pick-and-place resumed — simulating %.1fs remaining", self._simulation_duration)
        self._sim_timer = threading.Timer(self._simulation_duration, self._simulation_complete)
        self._sim_timer.daemon = True
        self._sim_timer.start()

    def _on_reset_errors(self) -> None:
        self._cancel_timer()

    # ── Simulation ────────────────────────────────────────────────────

    def _simulation_complete(self) -> None:
        """Called from the timer thread when simulated work is done."""
        self._logger.info("Pick-and-place simulation complete — stopping")
        self.stop()

    def _cancel_timer(self) -> None:
        if self._sim_timer is not None:
            self._sim_timer.cancel()
            self._sim_timer = None
