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

    def save_work_area(self, area_type: str, normalized_points) -> tuple:
        key = area_type.removesuffix("_area") if area_type.endswith("_area") else area_type
        w = self._settings.width or 1
        h = self._settings.height or 1
        pixel_points = [(round(x * w), round(y * h)) for x, y in normalized_points]
        return self._service.save_work_area(key, pixel_points)

    def get_work_area(self, area_type: str) -> list:
        key = area_type.removesuffix("_area") if area_type.endswith("_area") else area_type
        ok, _, points = self._service.get_work_area(key)
        if not ok or not points:
            return []
        w = self._settings.width or 1
        h = self._settings.height or 1
        return [(x / w, y / h) for x, y in points]

    @property
    def current_settings(self) -> CameraSettingsData:
        return self._settings
