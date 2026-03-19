import logging
from typing import Sequence
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

    def calibrate_camera_tcp_offset(self) -> tuple[bool, str]:
        _logger.info("Stub: calibrate_camera_tcp_offset")
        return True, "Stub: camera TCP offset calibrated"

    def stop_calibration(self) -> None:
        _logger.info("Stub: stop_calibration")

    def is_calibrated(self) -> bool:
        return False

    def test_calibration(self) -> tuple[bool, str]:
        _logger.info("Stub: test_calibration")
        return True, "Stub: test calibration complete"

    def stop_test_calibration(self) -> None:
        _logger.info("Stub: stop_test_calibration")

    def measure_marker_heights(self) -> tuple[bool, str]:
        _logger.info("Stub: measure_marker_heights")
        return True, "Stub: marker height mapping complete"

    def generate_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> list[tuple[float, float]]:
        _logger.info("Stub: generate_area_grid rows=%d cols=%d corners=%s", rows, cols, list(corners_norm))
        return [(0.2, 0.2), (0.5, 0.5), (0.8, 0.8)]

    def measure_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]:
        _logger.info("Stub: measure_area_grid rows=%d cols=%d corners=%s", rows, cols, list(corners_norm))
        return True, "Stub: area grid height mapping complete"

    def stop_marker_height_measurement(self) -> None:
        _logger.info("Stub: stop_marker_height_measurement")

    def can_measure_marker_heights(self) -> bool:
        return True

    def verify_height_model(self) -> tuple[bool, str]:
        _logger.info("Stub: verify_height_model")
        return True, "Stub: height model verification complete"

    def get_height_calibration_data(self):
        return None

    def has_saved_height_model(self) -> bool:
        return False

    def restore_pending_safety_walls(self) -> bool:
        _logger.info("Stub: restore_pending_safety_walls")
        return True
