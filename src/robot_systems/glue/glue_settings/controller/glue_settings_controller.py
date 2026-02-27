import logging

from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.glue.glue_settings.model.glue_settings_model import GlueSettingsModel
from src.robot_systems.glue.glue_settings.view.glue_settings_view import GlueSettingsView


class GlueSettingsController(IApplicationController):

    def __init__(self, model: GlueSettingsModel, view: GlueSettingsView):
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)

        self._view.save_requested.connect(self._on_save)
        self._view.spray_on_changed.connect(self._on_spray_on_changed)
        self._view.add_type_requested.connect(self._on_add_type)
        self._view.update_type_requested.connect(self._on_update_type)
        self._view.remove_type_requested.connect(self._on_remove_type)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        settings = self._model.load()
        self._view.load_settings(settings)
        self._reload_types()

    def stop(self) -> None:
        pass

    def _on_save(self, _values: dict) -> None:
        try:
            self._model.save(self._view.get_values())
            self._logger.info("Glue settings saved")
        except Exception:
            self._logger.exception("Failed to save glue settings")

    def _on_spray_on_changed(self, value: bool) -> None:
        try:
            flat = self._view.get_values()
            flat["spray_on"] = value
            self._model.save(flat)
            self._logger.info("spray_on auto-saved → %s", value)
        except Exception:
            self._logger.exception("Failed to auto-save spray_on")

    def _on_add_type(self, name: str, description: str) -> None:
        try:
            self._model.add_glue_type(name, description)
            self._reload_types()
        except Exception:
            self._logger.exception("Failed to add glue type '%s'", name)

    def _on_update_type(self, id_: str, name: str, description: str) -> None:
        try:
            self._model.update_glue_type(id_, name, description)
            self._reload_types()
        except Exception:
            self._logger.exception("Failed to update glue type '%s'", id_)

    def _on_remove_type(self, id_: str) -> None:
        try:
            self._model.remove_glue_type(id_)
            self._reload_types()
        except Exception:
            self._logger.exception("Failed to remove glue type '%s'", id_)

    def _reload_types(self) -> None:
        self._view.load_glue_types(self._model.load_glue_types())
