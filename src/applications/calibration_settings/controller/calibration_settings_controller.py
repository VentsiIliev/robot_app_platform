from src.applications.base.i_application_controller import IApplicationController
from src.applications.calibration_settings.mapper import CalibrationSettingsMapper
from src.applications.calibration_settings.model.calibration_settings_model import (
    CalibrationSettingsModel,
)
from src.applications.calibration_settings.view.calibration_settings_view import (
    CalibrationSettingsView,
)


class CalibrationSettingsController(IApplicationController):

    def __init__(self, model: CalibrationSettingsModel, view: CalibrationSettingsView, _messaging=None):
        self._model = model
        self._view = view

    def load(self) -> None:
        settings = self._model.load()
        self._view.settings_view.set_values(CalibrationSettingsMapper.to_flat_dict(settings))
        self._view.save_requested.connect(self._on_save)

    def stop(self) -> None:
        try:
            self._view.save_requested.disconnect(self._on_save)
        except Exception:
            pass

    def _on_save(self, flat: dict) -> None:
        updated = CalibrationSettingsMapper.from_flat_dict(flat, self._model.current_settings)
        self._model.save(updated)
