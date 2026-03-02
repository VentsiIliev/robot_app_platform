import logging
from typing import List, Tuple, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.robot_systems.glue.applications.workpiece_editor.model import WorkpieceEditorModel
from src.robot_systems.glue.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(QObject):
    camera_frame   = pyqtSignal(object)
    contours_ready = pyqtSignal(list)


class WorkpieceEditorController(IApplicationController):

    def __init__(self, model: WorkpieceEditorModel, view: WorkpieceEditorView,
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
        self._bridge.contours_ready.connect(self._view.update_contours)
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

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_camera_frame(self, frame) -> None:
        if self._active:
            self._view.update_camera_feed(frame)

    def _connect_signals(self) -> None:
        self._view.save_requested.connect(self._on_save)
        self._view.execute_requested.connect(self._on_execute)
        self._view.capture_requested.connect(self._on_capture)

    def _on_save(self, data: dict) -> None:
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece: %s — %s", ok, msg)

    def _on_execute(self, data: dict) -> None:
        ok, msg = self._model.execute_workpiece(data)
        self._logger.info("Execute workpiece: %s — %s", ok, msg)

    def _on_capture(self) -> None:
        contours = self._model.get_contours()
        self._bridge.contours_ready.emit(contours)

    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))