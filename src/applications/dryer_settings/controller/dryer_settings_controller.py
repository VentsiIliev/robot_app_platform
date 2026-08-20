from __future__ import annotations

import logging
from time import monotonic, sleep

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.dryer_settings.model.dryer_settings_model import DryerSettingsModel
from src.applications.dryer_settings.view.dryer_settings_view import DryerSettingsView


class DryerSettingsController(IApplicationController, BackgroundWorker):
    # QToggle's click animation is 500 ms. Keep a failed attempt visibly ON
    # long enough for that animation to finish before applying the rollback.
    _MIN_ENABLE_FEEDBACK_SECONDS = 0.65

    def __init__(self, model: DryerSettingsModel, view: DryerSettingsView) -> None:
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)
        self._pending_values: dict = {}
        self._enable_transition_running = False
        self._pending_enabled = False
        self._enable_attempt_started_at: float | None = None

        self._view.save_requested.connect(self._on_save)
        self._view.enabled_changed.connect(self._on_enabled_changed)
        self._view.refresh_status_requested.connect(self._on_refresh_status)
        self._view.move_servos_requested.connect(self._on_move_servos)
        self._view.open_plate_requested.connect(self._on_open_plate)
        self._view.close_plate_requested.connect(self._on_close_plate)
        self._view.next_position_requested.connect(self._on_next_position)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        config = self._model.load()
        self._view.load_config(config)
        self._view.set_enabled(self._model.is_enabled())

    def stop(self) -> None:
        self._stop_threads()

    def _on_save(self, values: dict) -> None:
        try:
            self._model.save(values)
            self._view.set_enabled(self._model.is_enabled())
            self._view.set_status("Saved")
        except Exception as exc:
            self._logger.exception("Failed to save dryer config")
            try:
                self._view.set_enabled(self._model.is_enabled())
            except Exception:
                self._logger.exception("Failed to refresh dryer enabled state")
            self._view.set_status(str(exc))

    def _on_enabled_changed(self, enabled: bool) -> None:
        self._logger.info(
            "Dryer toggle request received: requested=%s transition_running=%s",
            bool(enabled),
            self._enable_transition_running,
        )
        if self._enable_transition_running:
            self._logger.info(
                "Ignoring repeated dryer toggle request; restoring pending state=%s",
                self._pending_enabled,
            )
            self._view.set_enabled(self._pending_enabled)
            return
        self._enable_transition_running = True
        self._pending_enabled = bool(enabled)
        self._enable_attempt_started_at = monotonic() if enabled else None
        self._logger.info("Starting dryer %s transition", "enable" if enabled else "disable")
        self._view.set_busy(True)
        self._view.set_status("Enabling dryer…" if enabled else "Disabling dryer…")
        self._run_in_thread(
            fn=self._set_pending_enabled,
            on_done=self._on_enable_transition_finished,
            on_error=self._on_enable_failed,
        )

    def _set_pending_enabled(self) -> tuple[bool, bool, str]:
        try:
            enabled = self._model.set_enabled(self._pending_enabled)
            return True, bool(enabled), ""
        except Exception as exc:
            if self._pending_enabled and self._enable_attempt_started_at is not None:
                elapsed = monotonic() - self._enable_attempt_started_at
                remaining = self._MIN_ENABLE_FEEDBACK_SECONDS - elapsed
                if remaining > 0:
                    self._logger.info(
                        "Dryer enable failed; keeping toggle ON for %.0f ms before rollback",
                        remaining * 1000,
                    )
                    sleep(remaining)
            return False, False, str(exc)

    def _on_enable_transition_finished(self, result: tuple[bool, bool, str]) -> None:
        succeeded, enabled, message = result
        if succeeded:
            self._on_enabled_updated(enabled)
        else:
            self._on_enable_failed(message)

    def _on_enabled_updated(self, enabled: bool) -> None:
        self._logger.info("Dryer toggle transition succeeded: enabled=%s", bool(enabled))
        self._enable_transition_running = False
        self._enable_attempt_started_at = None
        self._view.set_busy(False)
        self._view.set_enabled(bool(enabled))
        self._view.set_status("Dryer enabled" if enabled else "Dryer disabled")

    def _on_enable_failed(self, message: str) -> None:
        self._logger.error("Dryer enable/disable failed: %s", message)
        self._finish_enable_failure(message)

    def _finish_enable_failure(self, message: str) -> None:
        self._logger.info("Applying dryer toggle rollback to OFF")
        self._enable_transition_running = False
        self._enable_attempt_started_at = None
        self._view.set_busy(False)
        # A failed lifecycle transition always leaves DryerService disabled.
        # Force the UI off instead of depending on a second settings read.
        self._view.set_enabled(False)
        self._logger.info("Dryer toggle rollback applied")
        self._view.set_error(f"Dryer enable failed: {message}")

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
