import logging
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.engine.vision.i_vision_service import IVisionService


class CalibrationApplicationService(ICalibrationService):

    def __init__(self, vision_service: IVisionService):
        self._vision_service = vision_service
        self._logger = logging.getLogger(self.__class__.__name__)

    def capture_calibration_image(self) -> tuple[bool, str]:
        return self._vision_service.capture_calibration_image()

    def calibrate_camera(self) -> tuple[bool, str]:
        return self._vision_service.calibrate_camera()

    def calibrate_robot(self) -> tuple[bool, str]:
        # TODO: wire to robot calibration service
        return False, "Robot calibration not yet implemented"

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        ok, msg = self.calibrate_camera()
        if not ok:
            return False, f"Camera calibration failed: {msg}"
        ok, msg = self.calibrate_robot()
        if not ok:
            return False, f"Robot calibration failed: {msg}"
        return True, "Camera and robot calibrated successfully"