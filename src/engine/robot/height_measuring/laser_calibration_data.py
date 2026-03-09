from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository


@dataclass
class LaserCalibrationData:
    zero_reference_coords: Optional[List[float]] = None
    robot_initial_position: Optional[List[float]] = None
    calibration_points: List[List[float]] = field(default_factory=list)
    polynomial_coefficients: List[float] = field(default_factory=list)
    polynomial_intercept: float = 0.0
    polynomial_degree: int = 1
    polynomial_mse: float = 0.0

    def is_calibrated(self) -> bool:
        return bool(self.polynomial_coefficients)


class LaserCalibrationDataSerializer(ISettingsSerializer[LaserCalibrationData]):

    @property
    def settings_type(self) -> str:
        return "laser_calibration_data"

    def get_default(self) -> LaserCalibrationData:
        return LaserCalibrationData()

    def to_dict(self, data: LaserCalibrationData) -> Dict[str, Any]:
        return {
            "zero_reference_coords":    data.zero_reference_coords,
            "robot_initial_position":   data.robot_initial_position,
            "calibration_points":       data.calibration_points,
            "polynomial_coefficients":  data.polynomial_coefficients,
            "polynomial_intercept":     data.polynomial_intercept,
            "polynomial_degree":        data.polynomial_degree,
            "polynomial_mse":           data.polynomial_mse,
        }

    def from_dict(self, raw: Dict[str, Any]) -> LaserCalibrationData:
        return LaserCalibrationData(
            zero_reference_coords=raw.get("zero_reference_coords"),
            robot_initial_position=raw.get("robot_initial_position"),
            calibration_points=raw.get("calibration_points", []),
            polynomial_coefficients=raw.get("polynomial_coefficients", []),
            polynomial_intercept=raw.get("polynomial_intercept", 0.0),
            polynomial_degree=raw.get("polynomial_degree", 1),
            polynomial_mse=raw.get("polynomial_mse", 0.0),
        )


class LaserCalibrationRepository(BaseJsonSettingsRepository[LaserCalibrationData]):
    def __init__(self, file_path: str):
        super().__init__(LaserCalibrationDataSerializer(), file_path)

