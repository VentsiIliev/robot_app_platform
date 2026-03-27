from __future__ import annotations

import threading
from typing import Callable, Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.system.i_system_manager import ISystemManager
from src.robot_systems.paint.component_ids import ProcessID

_SIMULATION_DURATION_S = 3.0


class PaintProcess(BaseProcess):

    def __init__(
        self,
        messaging: IMessagingService,
        system_manager: Optional[ISystemManager] = None,
        requirements: Optional[ProcessRequirements] = None,
        service_checker: Optional[Callable[[str], bool]] = None,
        simulation_duration_s: float = _SIMULATION_DURATION_S,
    ) -> None:
        super().__init__(
            process_id=ProcessID.MAIN_PROCESS,
            messaging=messaging,
            system_manager=system_manager,
            requirements=requirements or ProcessRequirements.none(),
            service_checker=service_checker,
        )
        self._simulation_duration_s = simulation_duration_s
        self._timer: Optional[threading.Timer] = None

    def _on_start(self) -> None:
        self._logger.info("PaintProcess started — simulating %.1fs of work", self._simulation_duration_s)
        self._start_timer()

    def _on_stop(self) -> None:
        self._cancel_timer()
        self._logger.info("PaintProcess stopped")

    def _on_pause(self) -> None:
        self._cancel_timer()
        self._logger.info("PaintProcess paused")

    def _on_resume(self) -> None:
        self._logger.info("PaintProcess resumed — simulating %.1fs of work", self._simulation_duration_s)
        self._start_timer()

    def _on_reset_errors(self) -> None:
        self._cancel_timer()
        self._logger.info("PaintProcess reset errors")

    def _start_timer(self) -> None:
        self._cancel_timer()
        self._timer = threading.Timer(self._simulation_duration_s, self._complete)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _complete(self) -> None:
        self._logger.info("PaintProcess simulation complete — stopping")
        self.stop()

