from abc import ABC, abstractmethod

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData


class ICalibrationSettingsService(ABC):

    @abstractmethod
    def load_settings(self) -> CalibrationSettingsData: ...

    @abstractmethod
    def save_settings(self, settings: CalibrationSettingsData) -> None: ...

    def capture_workobject_point(self, point_name: str) -> tuple[bool, str, dict]:
        return False, "WorkObject calibration is not configured", {}

    def solve_workobject(self, user_id: int, name: str = "") -> tuple[bool, str, dict]:
        return False, "WorkObject calibration is not configured", {}

    def save_workobject(self, user_id: int, name: str = "", persist: bool = True) -> tuple[bool, str, dict]:
        return False, "WorkObject calibration is not configured", {}
