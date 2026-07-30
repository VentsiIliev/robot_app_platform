from __future__ import annotations

import threading
from typing import Callable, Optional

from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.system.i_system_manager import ISystemManager
from src.robot_systems.paint.component_ids import ProcessID


class PaintProcess(BaseProcess):
    """Run one paint production cycle in the background and report process state changes."""
    def __init__(
        self,
        production_service,
        messaging: IMessagingService,
        robot_service: Optional[IRobotService] = None,
        vacuum_pump: Optional[IVacuumPumpController] = None,
        system_manager: Optional[ISystemManager] = None,
        requirements: Optional[ProcessRequirements] = None,
        service_checker: Optional[Callable[[str], bool]] = None,
    ) -> None:
        """Store the production service and process dependencies for a single-run paint process."""
        super().__init__(
            process_id=ProcessID.MAIN_PROCESS,
            messaging=messaging,
            system_manager=system_manager,
            requirements=requirements or ProcessRequirements.none(),
            service_checker=service_checker,
        )
        self._production_service = production_service
        self._robot_service = robot_service
        self._vacuum_pump = vacuum_pump
        self._thread: Optional[threading.Thread] = None
        self._stop_thread: Optional[threading.Thread] = None
        self._stopping = False

    def _on_start(self) -> None:
        """Start the background worker thread that performs one production cycle."""
        self._stopping = False
        self._thread = threading.Thread(
            target=self._run_in_background,
            daemon=True,
            name="PaintProcess",
        )
        self._thread.start()

    def _on_stop(self) -> None:
        """Signal stop and request hardware halt without blocking the process lock."""
        self._stopping = True
        self._request_hardware_stop()

    def _request_hardware_stop(self) -> None:
        thread = threading.Thread(
            target=self._stop_hardware,
            daemon=True,
            name="PaintProcessStop",
        )
        self._stop_thread = thread
        thread.start()

    def _stop_hardware(self) -> None:
        if self._robot_service is not None:
            try:
                self._robot_service.stop_motion()
            except Exception:
                self._logger.exception("Paint stop failed to stop robot motion")
        if self._vacuum_pump is not None:
            try:
                self._vacuum_pump.turn_off()
            except Exception:
                self._logger.exception("Paint stop failed to turn vacuum pump off")

    def _on_pause(self) -> None:
        """Ignore pause because the paint process currently has no resumable checkpoint model."""
        pass

    def _on_resume(self) -> None:
        """Ignore resume because pause is not implemented for this process."""
        pass

    def _on_reset_errors(self) -> None:
        """Clear the internal stop flag so a new run can be started after an error reset."""
        self._stopping = False

    def _run_in_background(self) -> None:
        """Execute one production cycle and translate the result into process state transitions."""
        try:
            success, msg = self._production_service.run_once(lambda: self._stopping)
        except Exception as exc:
            self._logger.exception("Paint process failed")
            if not self._stopping:
                self.set_error(str(exc))
            return

        if self._stopping:
            return

        if success:
            self._logger.info("Paint process completed: %s", msg)
            self.stop()
        else:
            self.set_error(msg)
