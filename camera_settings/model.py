from typing import Optional

from src.plugin.camera_settings.camera_settings_data import CameraSettingsData
from src.plugin.camera_settings.ICameraSettingsService import ISettingsPersistenceService


class CameraSettingsModel:
    def __init__(self, service: ISettingsPersistenceService):
        self._service = service
        self._settings: Optional[CameraSettingsData] = None

    def load(self) -> CameraSettingsData:
        self._settings = self._service.load_settings()
        return self._settings

    def save(self, settings: CameraSettingsData) -> None:
        self._service.save_settings(settings)
        self._settings = settings
