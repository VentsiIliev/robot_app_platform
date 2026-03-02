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

    def save_work_area(self, area_name: str, normalized_points: list) -> tuple[bool, str]:
        area_type = self._area_name_to_type(area_name)
        w, h = self._settings.width, self._settings.height
        pixel_points = [(int(x * w), int(y * h)) for x, y in normalized_points]
        return self._service.save_work_area(area_type, pixel_points)

    def get_work_area(self, area_name: str) -> list:
        area_type = self._area_name_to_type(area_name)
        ok, _, pixel_points = self._service.get_work_area(area_type)
        if not ok or pixel_points is None:
            return []
        w, h = self._settings.width, self._settings.height
        return [(px / w, py / h) for px, py in pixel_points]

    @property
    def current_settings(self) -> CameraSettingsData:
        return self._settings

    @staticmethod
    def _area_name_to_type(area_name: str) -> str:
        return area_name.replace("_area", "")
