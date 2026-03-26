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

    @property
    def current_settings(self) -> CalibrationSettingsData:
        assert self._settings is not None
        return self._settings
