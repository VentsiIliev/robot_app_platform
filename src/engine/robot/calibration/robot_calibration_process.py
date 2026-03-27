from __future__ import annotations
import threading
from typing import Callable, Optional

from src.engine.system.i_system_manager import ISystemManager
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.base_process import BaseProcess
from src.engine.process.process_requirements import ProcessRequirements
from src.engine.robot.calibration.i_robot_calibration_service import IRobotCalibrationService

_DEFAULT_PROCESS_ID = "robot_calibration"


class RobotCalibrationProcess(BaseProcess):
    """
    Runs IRobotCalibrationService.run_calibration() in a background thread.
    Transitions to STOPPED on success, ERROR on failure.
    _on_stop() signals stop_calibration() but does NOT join — called while the lock is held.
    """

    def __init__(
        self,
        calibration_service: IRobotCalibrationService,
        messaging:           IMessagingService,
        process_id:          str                          = _DEFAULT_PROCESS_ID,
        system_manager:      Optional[ISystemManager]    = None,
        requirements:        Optional[ProcessRequirements] = None,
        service_checker:     Optional[Callable[[str], bool]] = None,
    ):
        super().__init__(
            process_id      = process_id,
            messaging       = messaging,
            system_manager  = system_manager,
            requirements    = requirements,
            service_checker = service_checker,
        )

        self._calibration_service            = calibration_service
        self._thread: Optional[threading.Thread] = None
        self._stopping                        = False

    def _on_start(self) -> None:
        self._stopping = False
        self._thread = threading.Thread(
            target=self._run_in_background,
            daemon=True,
            name="RobotCalibrationProcess",
        )
        self._thread.start()

    def _on_stop(self) -> None:
        self._stopping = True
        self._calibration_service.stop_calibration()
        # Do NOT join here — _on_stop is called while the lock is held;
        # _run_in_background may be trying to acquire the same lock via stop()/set_error()

    def _on_pause(self) -> None:
        pass  # calibration cannot be meaningfully paused

    def _on_resume(self) -> None:
        pass

    def _on_reset_errors(self) -> None:
        self._stopping = False

    def _run_in_background(self) -> None:
        try:
            success, msg = self._calibration_service.run_calibration()
        except Exception as exc:
            self._logger.exception("Calibration thread raised an exception")
            if not self._stopping:
                self.set_error(str(exc))
            return

        if self._stopping:
            return

        if success:
            self._logger.info("Calibration finished successfully — stopping process")
            self.stop()
        else:
            self.set_error(msg)