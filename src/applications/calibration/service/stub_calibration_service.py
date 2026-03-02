import logging
from src.applications.calibration.service.i_calibration_service import ICalibrationService

_logger = logging.getLogger(__name__)


class StubCalibrationService(ICalibrationService):

    def capture_calibration_image(self) -> tuple[bool, str]:
        _logger.info("Stub: capture_calibration_image")
        return True, "Stub: calibration image captured"

    def calibrate_camera(self) -> tuple[bool, str]:
        _logger.info("Stub: calibrate_camera")
        return True, "Stub: camera calibrated"

    def calibrate_robot(self) -> tuple[bool, str]:
        _logger.info("Stub: calibrate_robot")
        return True, "Stub: robot calibrated"

    def calibrate_camera_and_robot(self) -> tuple[bool, str]:
        _logger.info("Stub: calibrate_camera_and_robot")
        return True, "Stub: camera and robot calibrated"