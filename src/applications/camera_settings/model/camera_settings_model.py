from src.applications.base.i_application_model import IApplicationModel
from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.service.i_camera_settings_service import ICameraSettingsService


class CameraSettingsModel(IApplicationModel):

    def __init__(self, service: ICameraSettingsService):
        self._service  = service
        self._settings = CameraSettingsData()

    def load(self) -> CameraSettingsData:
        self._settings = self._service.load_settings()
        return self._settings

    def save(self, settings: CameraSettingsData) -> None:
        self._service.save_settings(settings)
        self._settings = settings

    def set_raw_mode(self, enabled: bool) -> None:
        self._service.set_raw_mode(enabled)

    @property
    def current_settings(self) -> CameraSettingsData:
        return self._settings
