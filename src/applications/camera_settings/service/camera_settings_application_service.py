import logging
from src.applications.camera_settings.camera_settings_data import CameraSettingsData
from src.applications.camera_settings.mapper import CameraSettingsMapper
from src.applications.camera_settings.service.i_camera_settings_service import ICameraSettingsService
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.engine.vision.i_vision_service import IVisionService


class CameraSettingsApplicationService(ICameraSettingsService):

    def __init__(self, settings_service: ISettingsService, vision_service: IVisionService):
        self._settings_service = settings_service
        self._vision_service   = vision_service
        self._settings_id      = CommonSettingsID.VISION_CAMERA_SETTINGS
        self._logger           = logging.getLogger(self.__class__.__name__)

    def load_settings(self) -> CameraSettingsData:
        raw = self._settings_service.get(self._settings_id)
        return CameraSettingsMapper.from_json(raw.data)

    def save_settings(self, settings: CameraSettingsData) -> None:
        from src.engine.vision.camera_settings_serializer import CameraSettings
        raw = CameraSettings(data=CameraSettingsMapper.to_json(settings))
        self._settings_service.save(self._settings_id, raw)
        self._vision_service.update_settings(CameraSettingsMapper.to_json(settings))

    def set_raw_mode(self, enabled: bool) -> None:
        self._vision_service.set_raw_mode(enabled)

    def update_settings(self, settings: dict) -> tuple[bool, str]:
        return self._vision_service.update_settings(settings)

    def save_work_area(self, area_type: str, pixel_points) -> tuple[bool, str]:
        return self._vision_service.save_work_area(area_type, pixel_points)

    def get_work_area(self, area_type: str) -> tuple[bool, str, any]:
        return self._vision_service.get_work_area(area_type)
