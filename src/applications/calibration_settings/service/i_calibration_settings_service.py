from abc import ABC, abstractmethod

from src.applications.calibration_settings.calibration_settings_data import CalibrationSettingsData


class ICalibrationSettingsService(ABC):

    @abstractmethod
    def load_settings(self) -> CalibrationSettingsData: ...

    @abstractmethod
    def save_settings(self, settings: CalibrationSettingsData) -> None: ...
