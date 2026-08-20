from __future__ import annotations

import logging

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.dryer_settings.model.dryer_settings_model import DryerSettingsModel
from src.applications.dryer_settings.view.dryer_settings_view import DryerSettingsView


class DryerSettingsController(IApplicationController, BackgroundWorker):
    def __init__(self, model: DryerSettingsModel, view: DryerSettingsView) -> None:
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._pending_values: dict = {}

        self._view.save_requested.connect(self._on_save)
        self._view.refresh_status_requested.connect(self._on_refresh_status)
        self._view.move_servos_requested.connect(self._on_move_servos)
        self._view.open_plate_requested.connect(self._on_open_plate)
        self._view.close_plate_requested.connect(self._on_close_plate)
        self._view.next_position_requested.connect(self._on_next_position)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        config = self._model.load()
        self._view.load_config(config)

    def stop(self) -> None:
        self._stop_threads()

    def _on_save(self, values: dict) -> None:
        try:
            self._model.save(values)
            self._view.set_status("Saved")
        except Exception as exc:
            self._logger.exception("Failed to save dryer config")
            self._view.set_status(str(exc))

    def _on_refresh_status(self) -> None:
        self._pending_values = self._view.get_values()
        self._view.set_busy(True)
        self._run_in_thread(
            fn=self._read_pending_state,
            on_done=self._on_state_read,
            on_error=self._on_worker_failed,
        )

    def _on_move_servos(self) -> None:
        self._run_action("Move Servos", self._move_servos_pending)

    def _on_open_plate(self) -> None:
        self._run_action("Open Plate", self._open_plate_pending)

    def _on_close_plate(self) -> None:
        self._run_action("Close Plate", self._close_plate_pending)

    def _on_next_position(self) -> None:
        self._run_action("Next Position", self._next_position_pending)

    def _run_action(self, action: str, fn) -> None:
        self._pending_action = action
        self._pending_values = self._view.get_values()
        self._view.set_busy(True)
        self._run_in_thread(
            fn=fn,
            on_done=self._on_action_done,
            on_error=self._on_worker_failed,
        )

    def _read_pending_state(self):
        return self._model.get_state(self._pending_values)

    def _move_servos_pending(self) -> bool:
        return self._model.move_servos(self._pending_values)

    def _open_plate_pending(self) -> bool:
        return self._model.open_plate(self._pending_values)

    def _close_plate_pending(self) -> bool:
        return self._model.close_plate(self._pending_values)

    def _next_position_pending(self) -> bool:
        return self._model.next_position(self._pending_values)

    def _on_state_read(self, state) -> None:
        self._view.set_busy(False)
        self._view.set_state(state)

    def _on_action_done(self, success: bool) -> None:
        self._view.set_busy(False)
        self._view.set_action_result(getattr(self, "_pending_action", "Action"), bool(success))

    def _on_worker_failed(self, message: str) -> None:
        self._logger.error("Dryer operation failed: %s", message)
        self._view.set_busy(False)
        self._view.set_status(message)
