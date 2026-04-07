from __future__ import annotations

import logging
import threading
from typing import Optional

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.process.i_process import IProcess
from src.shared_contracts.events.process_events import ProcessBusyEvent, ProcessState, ProcessTopics
from src.robot_systems.welding.component_ids import ProcessID
from src.engine.robot.calibration.robot_calibration_process import RobotCalibrationProcess


class WeldingCalibrationCoordinator:
    """Manages the robot calibration process for the welding system."""

    def __init__(
        self,
        calibration_process: RobotCalibrationProcess,
        messaging: IMessagingService,
    ) -> None:
        self._calibration_process = calibration_process
        self._messaging = messaging
        self._active_process: Optional[IProcess] = None
        self._lock = threading.Lock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def calibrate(self) -> None:
        with self._lock:
            if self._active_process is not None and self._active_process.state in (
                ProcessState.RUNNING, ProcessState.PAUSED
            ):
                self._messaging.publish(
                    ProcessTopics.busy(ProcessID.ROBOT_CALIBRATION),
                    ProcessBusyEvent(
                        requested_by="calibration",
                        message="Cannot start calibration — calibration is already running",
                    ),
                )
                self._logger.warning("Calibration rejected — already running")
                return

            if self._calibration_process.state == ProcessState.ERROR:
                self._logger.info("Auto-resetting calibration from ERROR before start")
                self._calibration_process.reset_errors()

            self._active_process = self._calibration_process
            process = self._calibration_process

        process.start()

    def stop_calibration(self) -> None:
        with self._lock:
            if self._active_process is self._calibration_process:
                self._active_process = None
                process = self._calibration_process
            else:
                process = None

        if process is not None:
            process.stop()