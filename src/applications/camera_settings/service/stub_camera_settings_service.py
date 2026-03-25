import logging
from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.service.i_camera_settings_service import ICameraSettingsService

_logger = logging.getLogger(__name__)


class StubCameraSettingsService(ICameraSettingsService):

    def __init__(self):
        self._settings = CameraSettingsData()

    def load_settings(self) -> CameraSettingsData:
        return self._settings

    def save_settings(self, settings: CameraSettingsData) -> None:
        self._settings = settings
        _logger.info("StubCameraSettingsService: settings saved")

    def set_raw_mode(self, enabled: bool) -> None:
        _logger.info("StubCameraSettingsService: raw_mode=%s", enabled)

    def update_settings(self, settings: dict) -> tuple[bool, str]:
        _logger.info("StubCameraSettingsService: update_settings")
        return True, "Stub: settings updated"

    def save_work_area(self, area_type: str, points) -> tuple[bool, str]:
        _logger.info("StubCameraSettingsService: save_work_area area_type=%s", area_type)
        return True, "Stub: work area saved"

    def get_work_area(self, area_type: str) -> tuple[bool, str, list]:
        _logger.info("StubCameraSettingsService: get_work_area area_type=%s", area_type)
        return True, "Stub: work area retrieved", []
