from src.plugin.camera_settings.model import CameraSettingsModel
from src.plugin.camera_settings.ISettingsMapper import ISettingsMapper
from src.plugin.camera_settings.view.camera_settings_view import CameraSettingsView

_TOGGLE_KEYS = {
    "contour_detection",
    "draw_contours",
    "gaussian_blur",
    "dilate_enabled",
    "erode_enabled",
    "brightness_auto",
    "aruco_enabled",
    "aruco_flip_image",
}


class CameraSettingsController:
    def __init__(self, model: CameraSettingsModel, view: CameraSettingsView, mapper: ISettingsMapper):
        self._model = model
        self._view = view
        self._mapper = mapper

        self._view.save_requested.connect(self._on_save)
        self._view.value_changed_signal.connect(self._on_value_changed)

    def load(self) -> None:
        settings = self._model.load()
        self._view.settings_view.set_values(self._mapper.to_flat_dict(settings))

    def _on_value_changed(self, key: str, value, component_name: str) -> None:
        if key in _TOGGLE_KEYS:
            self._on_save(self._view.settings_view.get_values())

    def _on_save(self, flat: dict) -> None:
        current_settings = self._model._settings
        settings = self._mapper.from_flat_dict(flat, current_settings)
        self._model.save(settings)
        print(f"[controller] Camera settings saved successfully")
