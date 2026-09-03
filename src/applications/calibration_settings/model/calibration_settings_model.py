from src.applications.base.i_application_model import IApplicationModel
from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData
from src.applications.calibration_settings.service.i_calibration_settings_service import (
    ICalibrationSettingsService,
)


class CalibrationSettingsModel(IApplicationModel):

    def __init__(self, service: ICalibrationSettingsService):
        self._service = service
        self._settings: CalibrationSettingsData | None = None

    def load(self) -> CalibrationSettingsData:
        self._settings = self._service.load_settings()
        return self._settings

    def save(self, settings: CalibrationSettingsData) -> None:
        self._service.save_settings(settings)
        self._settings = settings

    def capture_workobject_point(self, point_name: str) -> tuple[bool, str, dict]:
        return self._service.capture_workobject_point(point_name)

    def solve_workobject(self, user_id: int, name: str = "") -> tuple[bool, str, dict]:
        return self._service.solve_workobject(user_id, name)

    def save_workobject(self, user_id: int, name: str = "", persist: bool = True) -> tuple[bool, str, dict]:
        return self._service.save_workobject(user_id, name=name, persist=persist)

    @property
    def current_settings(self) -> CalibrationSettingsData:
        assert self._settings is not None
        return self._settings
