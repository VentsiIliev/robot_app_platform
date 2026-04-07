from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.robot.calibration.calibration_navigation_service import CalibrationNavigationService
from src.engine.robot.calibration.robot_system_calibration_provider import (
    RobotSystemCalibrationProvider,
)


class WeldingRobotSystemCalibrationProvider(RobotSystemCalibrationProvider):
    """Welding adapter that supplies the welding-specific calibration move."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_calibration_navigation(self):
        work_area_service = self._robot_system.get_service(CommonServiceID.WORK_AREAS)
        return CalibrationNavigationService(
            self._robot_system.get_service(CommonServiceID.NAVIGATION),
            before_move=(lambda: work_area_service.set_active_area_id("spray")),
        )
