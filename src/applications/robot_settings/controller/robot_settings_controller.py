import logging

from src.applications.base.i_application_controller import IApplicationController
from src.applications.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.applications.robot_settings.view.robot_settings_view import RobotSettingsView


class RobotSettingsController(IApplicationController):

    def __init__(self, model: RobotSettingsModel, view: RobotSettingsView):
        self._model  = model
        self._view   = view
        self._logger = logging.getLogger(self.__class__.__name__)

        self._view.save_requested.connect(self._on_save)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        config, _ = self._model.load()
        self._view.load_config(config)
        self._view.load_movement_groups(config.movement_groups)

    def stop(self) -> None:
        pass

    def _on_save(self, _values: dict) -> None:
        try:
            flat            = self._view.get_values()
            movement_groups = self._view.get_movement_groups()
            self._logger.debug("Saving %d fields, %d movement groups", len(flat), len(movement_groups))
            self._model.save(flat, movement_groups)
            self._logger.info("Robot settings saved")
        except Exception:
            self._logger.exception("Failed to save robot settings")
