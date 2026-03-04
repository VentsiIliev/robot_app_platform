import logging
from typing import List, Tuple, Callable

from PyQt6.QtCore import QObject, pyqtSignal

from src.applications.base.i_application_controller import IApplicationController
from src.applications.workpiece_editor.model import WorkpieceEditorModel
from src.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics
from PyQt6.QtWidgets import QMessageBox
from src.applications.base.styled_message_box import show_warning
from src.shared_contracts.events.workpiece_events import WorkpieceTopics


class _Bridge(QObject):
    camera_frame       = pyqtSignal(object)
    load_workpiece_raw = pyqtSignal(dict)



class WorkpieceEditorController(IApplicationController):

    def __init__(self, model: WorkpieceEditorModel, view: WorkpieceEditorView,
                 messaging: IMessagingService):
        self._model  = model
        self._view   = view
        self._broker = messaging
        self._bridge = _Bridge()
        self._subs:  List[Tuple[str, Callable]] = []
        self._active = False
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        self._active = True
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.load_workpiece_raw.connect(self._on_load_workpiece_raw)  # ← add
        self._view.set_capture_handler(self._get_contours)
        self._view.set_save_callback(self._on_form_submit)
        self._connect_signals()
        self._subscribe()
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        try:
            self._bridge.camera_frame.disconnect()
        except (RuntimeError, TypeError):
            pass
        try:
            self._bridge.load_workpiece_raw.disconnect()
        except (RuntimeError, TypeError):
            pass
        for topic, cb in reversed(self._subs):
            try:
                self._broker.unsubscribe(topic, cb)
            except Exception:
                pass
        self._subs.clear()

    # ── Capture (synchronous) ─────────────────────────────────────────

    def _get_contours(self) -> list:
        contours = self._model.get_contours()
        self._logger.debug("Capture: got %d contours from vision", len(contours))
        return contours

    # ── Broker → Bridge ───────────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)
        self._sub(WorkpieceTopics.OPEN_IN_EDITOR, self._on_open_in_editor_raw)  # ← add

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_camera_frame(self, frame) -> None:
        if self._active:
            self._view.update_camera_feed(frame)

    # ── View → Model ──────────────────────────────────────────────────

    def _on_form_submit(self, form_data: dict):
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            editor_data = inner.workpiece_manager.export_editor_data()  # ← was from_manager
        except Exception:
            editor_data = None

        data = {"form_data": form_data, "editor_data": editor_data}
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece: %s — %s", ok, msg)
        if not ok:
            show_warning(self._view, "Cannot Save", msg)
            return False, msg
        return True, msg

    def _connect_signals(self) -> None:
        self._view.save_requested.connect(self._on_save)  # fallback if callback not used
        self._view.execute_requested.connect(self._on_execute)

    def _on_save(self, data: dict) -> None:
        # Fallback path — only fires if set_form_submit_callback wasn't honored
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece (fallback): %s — %s", ok, msg)
        if not ok:
            show_warning(self._view, "Cannot Save", msg)

    def _on_execute(self, data: dict) -> None:
        ok, msg = self._model.execute_workpiece(data)
        self._logger.info("Execute workpiece: %s — %s", ok, msg)


    def _sub(self, topic: str, cb: Callable) -> None:
        self._broker.subscribe(topic, cb)
        self._subs.append((topic, cb))

    def _on_open_in_editor_raw(self, payload) -> None:
        if isinstance(payload, dict) and "storage_id" in payload:
            self._bridge.load_workpiece_raw.emit(payload)
        elif isinstance(payload, dict):
            self._bridge.load_workpiece_raw.emit({"raw": payload, "storage_id": None})

    def _on_load_workpiece_raw(self, payload: dict) -> None:
        if not self._active:
            return
        try:
            from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter
            raw = payload.get("raw", payload)
            storage_id = payload.get("storage_id")
            editor_data = WorkpieceAdapter.from_raw(raw)
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            inner.workpiece_manager.clear_workpiece()
            inner.workpiece_manager.load_editor_data(editor_data, close_contour=False)
            self._view._editor.contourEditor.data = raw  # lazy form prefill
            self._model.set_editing(storage_id)
            self._logger.info("Loaded workpiece into editor (storage_id=%s)", storage_id)
        except Exception as exc:
            self._logger.exception("Failed to load workpiece: %s", exc)
            show_warning(self._view, "Load Failed", str(exc))