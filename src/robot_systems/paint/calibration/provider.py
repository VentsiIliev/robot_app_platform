from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.robot.calibration.calibration_navigation_service import CalibrationNavigationService
from src.engine.robot.calibration.robot_system_calibration_provider import (
    RobotSystemCalibrationProvider,
)


class PaintRobotSystemCalibrationProvider(RobotSystemCalibrationProvider):
    """Paint adapter that supplies the paint-specific calibration move."""

    _CALIBRATION_AREA_ID = "paint"

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_calibration_navigation(self):
        area_id = self._require_valid_area_id(self._CALIBRATION_AREA_ID)
        work_area_service = self._robot_system.get_service(CommonServiceID.WORK_AREAS)
        return CalibrationNavigationService(
            self._robot_system.get_service(CommonServiceID.NAVIGATION),
            before_move=(lambda: work_area_service.set_active_area_id(area_id)),
        )

    def _require_valid_area_id(self, area_id: str) -> str:
        normalized = str(area_id or "").strip()
        declared_area_ids = {
            str(definition.id).strip()
            for definition in self._robot_system.get_work_area_definitions()
            if str(definition.id).strip()
        }
        if normalized not in declared_area_ids:
            raise ValueError(
                f"Calibration area '{normalized}' is not declared for "
                f"{self._robot_system.__class__.__name__}. "
                f"Declared areas: {sorted(declared_area_ids)}"
            )
        return normalized
