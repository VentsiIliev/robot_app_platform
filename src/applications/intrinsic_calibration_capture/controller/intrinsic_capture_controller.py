from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.intrinsic_calibration_capture.model.intrinsic_capture_model import IntrinsicCaptureModel
from src.applications.intrinsic_calibration_capture.service.i_intrinsic_capture_service import (
    INTRINSIC_CAPTURE_PROGRESS_TOPIC,
)
from src.applications.intrinsic_calibration_capture.view.intrinsic_capture_view import IntrinsicCaptureView


class _Bridge(QObject):
    """Safely delivers broker callbacks to the Qt thread."""
    message_received = pyqtSignal(str)


class IntrinsicCaptureController(IApplicationController):

    def __init__(
        self,
        model: IntrinsicCaptureModel,
        view: IntrinsicCaptureView,
        messaging=None,
    ):
        self._model = model
        self._view = view
        self._messaging = messaging
        self._bridge = _Bridge()
        self._bridge.message_received.connect(self._on_progress_in_qt_thread)

    # ── IApplicationController ────────────────────────────────────────────────

    def load(self) -> None:
        self._view.set_config(self._model.get_config())
        self._view.start_requested.connect(self._on_start)
        self._view.stop_requested.connect(self._on_stop)
        self._view.save_config_requested.connect(self._model.save_config)

        if self._messaging is not None:
            self._messaging.subscribe(INTRINSIC_CAPTURE_PROGRESS_TOPIC, self._on_progress)

        # Live camera preview — update at ~10 fps
        from PyQt6.QtCore import QTimer
        self._preview_timer = QTimer()
        self._preview_timer.setInterval(100)
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start()

    def stop(self) -> None:
        self._preview_timer.stop()
        self._model.stop_capture()
        if self._messaging is not None:
            self._messaging.unsubscribe(INTRINSIC_CAPTURE_PROGRESS_TOPIC, self._on_progress)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _on_start(self) -> None:
        self._view.set_running(True)
        self._view.append_log("--- Starting acquisition ---")
        self._model.start_capture()
        # Poll for completion to re-enable buttons
        self._poll_running()

    def _on_stop(self) -> None:
        self._model.stop_capture()
        self._view.append_log("Stop requested.")

    def _on_progress(self, message: str) -> None:
        self._bridge.message_received.emit(message)

    def _on_progress_in_qt_thread(self, message: str) -> None:
        self._view.append_log(message)
        # Re-enable start button once acquisition finishes
        if not self._model.is_running():
            self._view.set_running(False)

    def _update_preview(self) -> None:
        frame = self._model.get_latest_frame()
        if frame is not None:
            self._view.set_frame(frame)

    def _poll_running(self) -> None:
        from PyQt6.QtCore import QTimer
        timer = QTimer()
        timer.setInterval(500)

        def _check():
            if not self._model.is_running():
                self._view.set_running(False)
                timer.stop()
                timer.deleteLater()

        timer.timeout.connect(_check)
        timer.start()
        self._timer = timer  # keep alive
