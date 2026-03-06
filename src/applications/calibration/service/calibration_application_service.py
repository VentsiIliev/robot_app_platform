import logging
from typing import Protocol

from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)


class _IProcessController(Protocol):
    def calibrate(self) -> None: ...
    def stop_calibration(self) -> None: ...


class CalibrationApplicationService(ICalibrationService):

    def __init__(self, vision_service: IVisionService, process_controller: _IProcessController):
        self._vision_service      = vision_service
        self._process_controller  = process_controller

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_service.capture_calibration_image()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_service.calibrate_camera()

    def calibrate_robot(self) -> tuple[bool, str]:
        self._process_controller.calibrate()
        return True, "Robot calibration started"

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        ok, msg = self.calibrate_camera()
        if not ok:
            return False, f"Camera calibration failed: {msg}"
        self._process_controller.calibrate()
        return True, "Camera calibrated — robot calibration started"

    def stop_calibration(self) -> None:
        self._process_controller.stop_calibration()
