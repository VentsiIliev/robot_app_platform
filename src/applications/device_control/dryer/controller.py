from __future__ import annotations

import logging

from src.applications.base.i_application_controller import IApplicationController
from src.applications.device_control.dryer.model import DryerControlModel
from src.applications.device_control.dryer.view import DryerControlPanel


class DryerControlController(IApplicationController):
    def __init__(self, model: DryerControlModel, view: DryerControlPanel) -> None:
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)

        self._view.save_requested.connect(self._on_save)

    def load(self) -> None:
        config = self._model.load()
        self._view.load_config(config)

    def stop(self) -> None:
        pass

    def _on_save(self, values: dict) -> None:
        try:
            self._model.save(values)
            self._view.set_status("Saved")
        except Exception as exc:
            self._logger.exception("Failed to save dryer config")
            self._view.set_status(str(exc))
