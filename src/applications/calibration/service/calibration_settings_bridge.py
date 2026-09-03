from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration_settings.service.i_calibration_settings_service import (
    ICalibrationSettingsService,
)


class CalibrationSettingsBridge:
    def __init__(self, service: ICalibrationSettingsService | None):
        self._service = service

    def load(self) -> CalibrationSettingsData | None:
        if self._service is None:
            return None
        return self._service.load_settings()

    def save(self, settings: CalibrationSettingsData) -> None:
        if self._service is None:
            return
        self._service.save_settings(settings)

    def capture_workobject_point(self, point_name: str) -> tuple[bool, str, dict]:
        if self._service is None:
            return False, "WorkObject calibration is not configured", {}
        return self._service.capture_workobject_point(point_name)

    def solve_workobject(self, user_id: int, name: str = "") -> tuple[bool, str, dict]:
        if self._service is None:
            return False, "WorkObject calibration is not configured", {}
        return self._service.solve_workobject(user_id, name)

    def save_workobject(self, user_id: int, name: str = "", persist: bool = True) -> tuple[bool, str, dict]:
        if self._service is None:
            return False, "WorkObject calibration is not configured", {}
        return self._service.save_workobject(user_id, name=name, persist=persist)
