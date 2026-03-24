import logging

from src.applications.base.i_application_controller import IApplicationController
from src.applications.height_measuring.model.height_measuring_model import HeightMeasuringModel
from src.applications.height_measuring.model.mapper import HeightMeasuringSettingsMapper
from src.applications.height_measuring.view.height_measuring_view import HeightMeasuringView

_logger = logging.getLogger(__name__)


class HeightMeasuringController(IApplicationController):
    def __init__(self, model, view, messaging):
        self._model = model
        self._view = view
        self._messaging = messaging
        self._view.save_settings_requested.connect(self._on_save_settings)

    def is_calibrating(self) -> bool:
        return False

    def load(self) -> None:
        settings = self._model.get_settings()
        self._view.set_settings(settings)
        self._view.load_settings(HeightMeasuringSettingsMapper.to_flat_dict(settings))
        is_cal = self._model.is_calibrated()
        info = self._model.get_calibration_info() if is_cal else None
        self._view.set_calibration_status(is_cal, info)

    def stop(self) -> None:
        self._model.cleanup()

    def _on_save_settings(self) -> None:
        flat = self._view.get_settings_values()
        base = self._model.get_settings()
        updated = HeightMeasuringSettingsMapper.from_flat_dict(flat, base)
        updated.calibration.calibration_initial_position = self._view.get_initial_position()
        ok, msg = self._model.save_settings(updated)
        self._view.show_message(msg, is_error=not ok)
