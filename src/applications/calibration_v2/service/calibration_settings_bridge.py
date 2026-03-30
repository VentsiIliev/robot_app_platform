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
