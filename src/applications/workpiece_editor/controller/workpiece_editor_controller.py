import logging
from typing import List, Tuple, Callable

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QLabel, QScrollArea, QVBoxLayout, QPushButton, QHBoxLayout

from src.applications.base.i_application_controller import IApplicationController
from src.applications.workpiece_editor.model import WorkpieceEditorModel
from src.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics
from src.applications.base.styled_message_box import show_warning, show_info, show_critical
from src.shared_contracts.events.workpiece_events import WorkpieceTopics


class _Bridge(QObject):
    camera_frame       = pyqtSignal(object)
    load_workpiece_raw = pyqtSignal(dict)


class WorkpieceEditorController(IApplicationController):

    def __init__(self, model: WorkpieceEditorModel, view: WorkpieceEditorView,
                 messaging: IMessagingService):
        self._model          = model
        self._view           = view
        self._broker         = messaging
        self._bridge         = _Bridge()
        self._subs:          List[Tuple[str, Callable]] = []
        self._active         = False
        self._camera_active  = True          # ← controls whether feed updates are forwarded
        self._logger         = logging.getLogger(self.__class__.__name__)
        self._preview_dialog = None

    def load(self) -> None:
        self._active        = True
        self._camera_active = True
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.load_workpiece_raw.connect(self._on_load_workpiece_raw)
        self._view.set_capture_handler(self._on_capture)   # ← renamed
        self._view.set_save_callback(self._on_form_submit)
        self._connect_signals()
        self._subscribe()
        self._view.destroyed.connect(self.stop)
        self._connect_segment_added()

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

        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            bus = getattr(inner, '_event_bus', None)
            if bus is not None and hasattr(bus, 'segment_added'):
                try:
                    bus.segment_added.disconnect(self._on_segment_added)
                except (RuntimeError, TypeError):
                    pass
        except Exception:
            pass

        self._subs.clear()

    # ── Capture ───────────────────────────────────────────────────────

    def _on_capture(self) -> list:
        """Called by the editor's capture button. Picks the largest contour,
        stops the live feed and loads the contour into the Workpiece layer."""
        contours = self._model.get_contours()
        self._logger.debug("Capture: got %d contours from vision", len(contours))
        largest = self._pick_largest(contours)
        if largest is None:
            self._logger.warning("Capture: no usable contour found")
            show_warning(self._view, "Capture", "No contour detected.\nMake sure the vision vision_service is running.")
            return []

        self._logger.debug("Capture: largest contour has %d points", len(largest))

        # Stop live camera feed so the captured frame stays visible
        self._camera_active = False

        try:
            from src.applications.workpiece_editor.editor_core.handlers.CaptureDataHandler import CaptureDataHandler
            editor_frame = self._view._editor
            inner = editor_frame.contourEditor.editor_with_rulers.editor
            wm = inner.workpiece_manager

            wm.clear_workpiece()

            editor_data = CaptureDataHandler.from_capture_data(
                contours=largest,
                metadata={"source": "camera_capture"},
            )

            wm.load_editor_data(editor_data, close_contour=True)

            editor_frame.pointManagerWidget.refresh_points()
            inner.update()

        except Exception:
            self._logger.exception("Capture: failed to load contour into editor")

        return [largest]

    @staticmethod
    def _pick_largest(contours: list):
        import cv2
        import numpy as np
        if not contours:
            return None
        best, best_area = None, -1.0
        for c in contours:
            try:
                arr = np.array(c, dtype=np.float32)
                area = float(cv2.contourArea(arr))
                if area > best_area:
                    best_area = area
                    best = arr
            except Exception:
                import traceback
                traceback.print_exc()
                continue
        return best

    # ── Broker → Bridge ───────────────────────────────────────────────

    def _subscribe(self) -> None:
        self._sub(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)
        self._sub(WorkpieceTopics.OPEN_IN_EDITOR, self._on_open_in_editor_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_camera_frame(self, frame) -> None:
        if not self._active or not self._camera_active or frame is None:
            return
        try:
            import cv2
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except Exception:
            rgb = frame
        self._view.update_camera_feed(rgb)

    # ── View → Model ──────────────────────────────────────────────────

    def _on_form_submit(self, form_data: dict):
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            editor_data = inner.workpiece_manager.export_editor_data()
        except Exception:
            editor_data = None

        data = {"form_data": form_data, "editor_data": editor_data}
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece: %s — %s", ok, msg)
        if not ok:
            show_warning(self._view, "Cannot Save", msg)
            return False, msg
        # Resume live feed after successful save
        self._camera_active = True
        return True, msg

    def _connect_signals(self) -> None:
        self._view.save_requested.connect(self._on_save)
        self._view.execute_requested.connect(self._on_execute)

    def _on_save(self, data: dict) -> None:
        ok, msg = self._model.save_workpiece(data)
        self._logger.info("Save workpiece (fallback): %s — %s", ok, msg)
        if not ok:
            show_warning(self._view, "Cannot Save", msg)

    def _on_execute(self, data: dict) -> None:
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            editor_data = inner.workpiece_manager.export_editor_data()
        except Exception:
            editor_data = None
        payload = {"form_data": data, "editor_data": editor_data}
        ok, msg = self._model.execute_workpiece(payload)
        self._logger.info("Execute workpiece: %s — %s", ok, msg)
        if ok:
            try:
                preview_contours = self._model.get_last_interpolation_preview_contours()
                if preview_contours:
                    self._view.update_contours(preview_contours)
                original_paths = self._model.get_last_original_preview_paths()
                pre_smoothed_paths = self._model.get_last_pre_smoothed_preview_paths()
                linear_paths = self._model.get_last_linear_preview_paths()
                preview_paths = self._model.get_last_interpolation_preview_paths()
                execution_paths = self._model.get_last_execution_preview_paths()
                if original_paths or preview_paths:
                    self._show_interpolation_plot(
                        original_paths,
                        pre_smoothed_paths,
                        linear_paths,
                        preview_paths,
                        execution_paths,
                    )
            except Exception:
                self._logger.debug("Failed to update interpolation preview contours", exc_info=True)

    def _show_interpolation_plot(
        self,
        original_paths: list[list[list[float]]],
        pre_smoothed_paths: list[list[list[float]]],
        linear_paths: list[list[list[float]]],
        preview_paths: list[list[list[float]]],
        execution_paths: list[list[list[float]]],
    ) -> None:
        from src.engine.robot.path_interpolation.debug_plotting import plot_trajectory_debug

        image_path = plot_trajectory_debug(
            original_paths,
            linear_paths,
            preview_paths,
            execution_paths,
            pre_smoothed_paths=pre_smoothed_paths,
        )
        if not image_path:
            return

        dialog = QDialog(self._view)
        dialog.setWindowTitle("Interpolated Path Preview")
        dialog.resize(1100, 800)

        layout = QVBoxLayout(dialog)
        scroll = QScrollArea(dialog)
        image_label = QLabel(scroll)
        pixmap = QPixmap(image_path)
        image_label.setPixmap(pixmap)
        image_label.setScaledContents(False)
        scroll.setWidget(image_label)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        execute_btn = QPushButton("Execute")
        execute_btn.clicked.connect(self._on_execute_preview_confirmed)
        button_row.addWidget(execute_btn)
        layout.addLayout(button_row)

        self._preview_dialog = dialog
        dialog.show()

    def _on_execute_preview_confirmed(self) -> None:
        ok, msg = self._model.execute_last_preview_paths()
        self._logger.info("Execute preview paths: %s — %s", ok, msg)
        if ok:
            show_info(self._preview_dialog or self._view, "Execution Started", msg)
        else:
            show_critical(self._preview_dialog or self._view, "Execution Failed", msg)

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
            raw        = payload.get("raw", payload)
            storage_id = payload.get("storage_id")
            editor_data = WorkpieceAdapter.from_raw(raw)
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            inner.workpiece_manager.clear_workpiece()
            inner.workpiece_manager.load_editor_data(editor_data, close_contour=False)
            self._view._editor.contourEditor.data = raw
            self._model.set_editing(storage_id)
            self._logger.info("Loaded workpiece into editor (storage_id=%s)", storage_id)
        except Exception as exc:
            self._logger.exception("Failed to load workpiece: %s", exc)
            show_warning(self._view, "Load Failed", str(exc))

    def _connect_segment_added(self) -> None:
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            bus = getattr(inner, '_event_bus', None)
            if bus is not None and hasattr(bus, 'segment_added'):
                bus.segment_added.connect(self._on_segment_added)
        except Exception:
            self._logger.debug("Could not connect segment_added event", exc_info=True)

    def _on_segment_added(self, *_args) -> None:
        """Called when the user draws a new segment — assign defaults to it immediately."""
        try:
            inner = self._view._editor.contourEditor.editor_with_rulers.editor
            if hasattr(inner, 'workpiece_manager'):
                inner.workpiece_manager.apply_defaults_to_segments_without_settings()
        except Exception:
            self._logger.debug("_on_segment_added: could not apply defaults", exc_info=True)
