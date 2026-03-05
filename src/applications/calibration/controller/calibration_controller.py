import logging
from typing import List, Tuple, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.calibration.model.calibration_model import CalibrationModel
from src.applications.calibration.view.calibration_view import CalibrationView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(QObject):
    camera_frame = pyqtSignal(object)


class CalibrationController(IApplicationController):

    def __init__(self, model: CalibrationModel, view: CalibrationView,
                 messaging: IMessagingService):
        self._model   = model
        self._view    = view
        self._broker  = messaging
        self._bridge  = _Bridge()
        self._subs:   List[Tuple[str, Callable]] = []
        self._active  = False
        self._logger  = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        self._active = True
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._connect_signals()
        self._subscribe()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass
        self._subs.clear()

    # ── Broker → Bridge ───────────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    # ── Bridge → View (main thread) ───────────────────────────────────

    def _on_camera_frame(self, frame) -> None:
        if self._active and frame is not None:  # ← add `and frame is not None`
            self._view.update_camera_view(frame)

    # ── View → Model ──────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.capture_requested.connect(self._on_capture)
        self._view.calibrate_camera_requested.connect(self._on_calibrate_camera)
        self._view.calibrate_robot_requested.connect(self._on_calibrate_robot)
        self._view.calibrate_sequence_requested.connect(self._on_calibrate_sequence)

    def _on_capture(self) -> None:
        ok, msg = self._model.capture_calibration_image()
        self._log(ok, msg)

    def _on_calibrate_camera(self) -> None:
        ok, msg = self._model.calibrate_camera()
        self._log(ok, msg)

    def _on_calibrate_robot(self) -> None:
        ok, msg = self._model.calibrate_robot()
        self._log(ok, msg)

    def _on_calibrate_sequence(self) -> None:
        ok, msg = self._model.calibrate_camera_and_robot()
        self._log(ok, msg)

    def _log(self, ok: bool, msg: str) -> None:
        prefix = "✓" if ok else "✗"
        self._view.append_log(f"{prefix} {msg}")

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))
