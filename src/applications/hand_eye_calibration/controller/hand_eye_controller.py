from __future__ import annotations

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.hand_eye_calibration.model.hand_eye_model import HandEyeModel
from src.applications.hand_eye_calibration.service.i_hand_eye_service import (
    HAND_EYE_COMPLETE_TOPIC,
    HAND_EYE_PROGRESS_TOPIC,
    HAND_EYE_SAMPLE_COUNT_TOPIC,
)
from src.applications.hand_eye_calibration.view.hand_eye_view import HandEyeView


class _Bridge(QObject):
    """Safely delivers broker callbacks to the Qt main thread."""
    message_received = pyqtSignal(str)
    complete_received = pyqtSignal(str)
    sample_count_received = pyqtSignal(int)


class HandEyeController(IApplicationController):

    def __init__(self, model: HandEyeModel, view: HandEyeView, messaging=None):
        self._model = model
        self._view = view
        self._messaging = messaging
        self._bridge = _Bridge()
        self._bridge.message_received.connect(self._on_progress_qt)
        self._bridge.complete_received.connect(self._on_complete_qt)
        self._bridge.sample_count_received.connect(self._view.set_sample_count)
        self._preview_timer: QTimer | None = None
        self._poll_timer: QTimer | None = None

    # ── IApplicationController ────────────────────────────────────────────────

    def load(self) -> None:
        self._view.set_config(self._model.get_config())
        self._view.start_requested.connect(self._on_start)
        self._view.stop_requested.connect(self._on_stop)
        self._view.save_config_requested.connect(self._model.save_config)

        if self._messaging is not None:
            self._messaging.subscribe(HAND_EYE_PROGRESS_TOPIC, self._on_progress)
            self._messaging.subscribe(HAND_EYE_COMPLETE_TOPIC, self._on_complete)
            self._messaging.subscribe(HAND_EYE_SAMPLE_COUNT_TOPIC, self._on_sample_count)

        self._preview_timer = QTimer()
        self._preview_timer.setInterval(100)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start()

    def stop(self) -> None:
        if self._preview_timer is not None:
            self._preview_timer.stop()
        if self._poll_timer is not None:
            self._poll_timer.stop()
        self._model.stop_capture()
        if self._messaging is not None:
            self._messaging.unsubscribe(HAND_EYE_PROGRESS_TOPIC, self._on_progress)
            self._messaging.unsubscribe(HAND_EYE_COMPLETE_TOPIC, self._on_complete)
            self._messaging.unsubscribe(HAND_EYE_SAMPLE_COUNT_TOPIC, self._on_sample_count)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_start(self) -> None:
        self._view.set_running(True)
        self._view.append_log("--- Starting hand-eye calibration ---")
        self._model.start_capture()
        self._start_poll()

    def _on_stop(self) -> None:
        self._model.stop_capture()
        self._view.append_log("Stop requested.")

    def _on_progress(self, message: str) -> None:
        self._bridge.message_received.emit(str(message))

    def _on_complete(self, message: str) -> None:
        self._bridge.complete_received.emit(str(message))

    def _on_sample_count(self, n) -> None:
        self._bridge.sample_count_received.emit(int(n))

    def _on_progress_qt(self, message: str) -> None:
        self._view.append_log(message)

    def _on_complete_qt(self, message: str) -> None:
        if message:
            self._view.append_log(message)
        self._view.set_running(False)

    def _update_preview(self) -> None:
        frame = self._model.get_latest_annotated_frame()
        if frame is not None:
            self._view.set_frame(frame)

    def _start_poll(self) -> None:
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(500)

        def _check():
            if not self._model.is_running():
                self._view.set_running(False)
                self._poll_timer.stop()

        self._poll_timer.timeout.connect(_check)
        self._poll_timer.start()
