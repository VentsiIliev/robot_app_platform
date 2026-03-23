from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.robot.calibration.calibration_navigation_service import CalibrationNavigationService
from src.engine.robot.calibration.robot_system_calibration_provider import (
    RobotSystemCalibrationProvider,
)


class GlueRobotSystemCalibrationProvider(RobotSystemCalibrationProvider):
    """Glue adapter that supplies the glue-specific calibration move."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_calibration_navigation(self):
        vision_service = self._robot_system.get_optional_service(CommonServiceID.VISION)
        return CalibrationNavigationService(
            self._robot_system.get_service(CommonServiceID.NAVIGATION),
            before_move=(lambda: vision_service.set_detection_area("spray")) if vision_service is not None else None,
        )
