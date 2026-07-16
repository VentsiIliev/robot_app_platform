from PyQt6.QtCore import QCoreApplication

from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.paint.applications.paint_process_settings.mapper import (
    PaintProcessSettingsMapper,
)
from src.robot_systems.paint.applications.paint_process_settings.model.paint_process_settings_model import (
    PaintProcessSettingsModel,
)
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_view import (
    PaintProcessSettingsView,
)


class PaintProcessSettingsController(IApplicationController):
    def __init__(self, model: PaintProcessSettingsModel, view: PaintProcessSettingsView):
        self._model = model
        self._view = view

    def load(self) -> None:
        settings = self._model.load()
        self._view.set_values(PaintProcessSettingsMapper.to_flat_dict(settings))
        self._view.save_requested.connect(self._on_save)

    def stop(self) -> None:
        try:
            self._view.save_requested.disconnect(self._on_save)
        except Exception:
            pass

    def _on_save(self, flat: dict) -> None:
        updated = PaintProcessSettingsMapper.from_flat_dict(flat, self._model.current_settings)
        self._model.save(updated)
        self._view.set_status(self._t("Saved. Changes will be used by the next Paint cycle."))

    @staticmethod
    def _t(text: str) -> str:
        translated = QCoreApplication.translate("PaintProcessSettings", text)
        return translated or text
