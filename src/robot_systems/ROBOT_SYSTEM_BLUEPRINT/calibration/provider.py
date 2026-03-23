from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.robot.calibration import CalibrationNavigationService
from src.engine.robot.calibration import RobotSystemCalibrationProvider


class MyRobotSystemCalibrationProvider(RobotSystemCalibrationProvider):
    """Build the calibration-navigation adapter for this robot system."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_calibration_navigation(self):
        return CalibrationNavigationService(
            self._robot_system.get_service(CommonServiceID.NAVIGATION),
            before_move=self._before_move,
        )

    def _before_move(self) -> None:
        # TODO: Add any robot-system-specific side effect needed before the
        # calibration move, or replace this with `None` if not needed.
        #
        # Example:
        # vision_service = self._robot_system.get_optional_service(CommonServiceID.VISION)
        # if vision_service is not None:
        #     vision_service.set_detection_area("my_calibration_area")
        pass
