import logging
from typing import Callable, Sequence
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration.service.i_calibration_service import ICalibrationService
from src.engine.robot.configuration import RobotCalibrationSettings
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettings
from src.shared_contracts.declarations import WorkAreaDefinition

_logger = logging.getLogger(__name__)


class StubCalibrationService(ICalibrationService):
    def load_calibration_settings(self) -> CalibrationSettingsData | None:
        return CalibrationSettingsData(
            vision=CalibrationVisionSettings(),
            robot=RobotCalibrationSettings(),
            height=HeightMeasuringModuleSettings(),
        )

    def save_calibration_settings(self, settings: CalibrationSettingsData) -> None:
        _logger.info("Stub: save_calibration_settings %s", settings)

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

    def calibrate_laser(self) -> tuple[bool, str]:
        _logger.info("Stub: calibrate_laser")
        return True, "Stub: laser calibrated"

    def detect_laser_once(self):
        from src.applications.height_measuring.service.i_height_measuring_app_service import LaserDetectionResult
        _logger.info("Stub: detect_laser_once")
        return LaserDetectionResult(ok=True, message="Stub: laser detected")

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

    def get_work_area_definitions(self) -> list[WorkAreaDefinition]:
        return [
            WorkAreaDefinition(
                id="default",
                label="Default",
                color="#4CAF50",
                supports_height_mapping=True,
            )
        ]

    def get_active_work_area_id(self) -> str:
        return "default"

    def set_active_work_area_id(self, area_id: str) -> None:
        _logger.info("Stub: set_active_work_area_id %s", area_id)

    def save_height_mapping_area(
        self,
        area_key: str,
        corners_norm: Sequence[tuple[float, float]],
    ) -> tuple[bool, str]:
        _logger.info("Stub: save_height_mapping_area %s %s", area_key, list(corners_norm))
        return True, "Stub: saved height mapping area"

    def get_height_mapping_area(self, area_key: str) -> list[tuple[float, float]]:
        _logger.info("Stub: get_height_mapping_area %s", area_key)
        return []

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
        area_id: str,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
    ) -> tuple[bool, str]:
        _logger.info("Stub: measure_area_grid area=%s rows=%d cols=%d corners=%s", area_id, rows, cols, list(corners_norm))
        return True, "Stub: area grid height mapping complete"

    def verify_area_grid(
        self,
        corners_norm: Sequence[tuple[float, float]],
        rows: int,
        cols: int,
        progress_callback: Callable[[str, str, int, int], None] | None = None,
    ) -> tuple[bool, str, dict]:
        _logger.info("Stub: verify_area_grid rows=%d cols=%d corners=%s", rows, cols, list(corners_norm))
        if progress_callback is not None:
            progress_callback("r1c1", "direct", 1, 3)
            progress_callback("r1c2", "via_anchor", 2, 3)
            progress_callback("r1c3", "unreachable", 3, 3)
        return True, "Stub: area grid verification complete", {
            "direct_labels": ["r1c1"],
            "via_anchor_labels": ["r1c2"],
            "unreachable_labels": ["r1c3"],
        }

    def ensure_active_work_area_observed(self) -> tuple[bool, str]:
        return True, ""

    def stop_marker_height_measurement(self) -> None:
        _logger.info("Stub: stop_marker_height_measurement")

    def can_measure_marker_heights(self) -> bool:
        return True

    def verify_height_model(self, area_id: str = "") -> tuple[bool, str]:
        _logger.info("Stub: verify_height_model area=%s", area_id)
        return True, "Stub: height model verification complete"

    def get_height_calibration_data(self, area_id: str = ""):
        return None

    def has_saved_height_model(self, area_id: str = "") -> bool:
        return False

    def restore_pending_safety_walls(self) -> bool:
        _logger.info("Stub: restore_pending_safety_walls")
        return True
