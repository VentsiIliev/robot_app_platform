import logging

from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal
from contour_editor import BezierSegmentManager

from src.applications.workpiece_editor.editor_core.config import (
    WorkpieceFormSchema, WorkpieceFormFactory, SegmentEditorConfig,
)
from src.applications.workpiece_editor.editor_core.adapters.i_workpiece_data_adapter import IWorkpieceDataAdapter
from src.applications.workpiece_editor.editor_core import WorkpieceEditorBuilder
from src.applications.workpiece_editor.editor_core.config.virtual_keyboard_widget_factory import \
    VirtualKeyboardWidgetFactory
from src.applications.base.i_application_view import IApplicationView

_logger = logging.getLogger(__name__)


class WorkpieceEditorView(IApplicationView):

    save_requested    = pyqtSignal(dict)
    execute_requested = pyqtSignal(dict)

    def __init__(self, schema: WorkpieceFormSchema, segment_config: SegmentEditorConfig, workpiece_data_adapter: IWorkpieceDataAdapter, parent=None):
        self._schema          = schema
        self._segment_config  = segment_config
        self._workpiece_data_adapter = workpiece_data_adapter
        self._editor          = None
        self._capture_handler = None
        super().__init__("WorkpieceEditor", parent)

    def setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        try:
            self._editor = self._build_editor()
            layout.addWidget(self._editor)
        except Exception as exc:
            _logger.exception("WorkpieceEditorView: failed to build editor")
            layout.addWidget(QLabel(f"WorkpieceEditor failed:\n{exc}"))

    def clean_up(self) -> None:
        if self._editor is None:
            return
        try:
            inner = (
                self._editor
                .contourEditor
                .editor_with_rulers
                .editor
            )
            if hasattr(inner, '_event_bus') and inner._event_bus is not None:
                bus = inner._event_bus
                for sig_name in (
                        "segment_visibility_changed",
                        "segment_deleted",
                        "segment_added",
                        "segment_layer_changed",
                        "points_changed",
                        "undo_executed",
                        "redo_executed",
                ):
                    sig = getattr(bus, sig_name, None)
                    if sig is not None:
                        try:
                            sig.disconnect()
                        except (RuntimeError, TypeError):
                            pass
        except (RuntimeError, AttributeError):
            pass
        self._editor = None

    def _build_editor(self):
        return (
            WorkpieceEditorBuilder()
            .with_segment_manager(BezierSegmentManager)
            .with_settings(
                self._segment_config.settings_config,
                self._segment_config.settings_provider,
            )
            .with_layer_config(self._schema.editor_layer_config)
            .with_form(WorkpieceFormFactory(schema=self._schema))
            .with_widgets(VirtualKeyboardWidgetFactory())
            .with_workpiece_data_adapter(self._workpiece_data_adapter)
            .on_save(self._on_save_cb)
            .on_capture(self._on_capture_cb)
            .on_execute(self._on_execute_cb)
            .on_update_camera_feed(self._on_camera_feed_cb)
            .build()
        )

    def set_capture_handler(self, handler) -> None:
        self._capture_handler = handler

    def set_save_callback(self, callback) -> None:
        if self._editor is not None:
            self._editor.set_form_submit_callback(callback)

    # ── Callbacks ────────────────────────────────────────────────────

    def _on_save_cb(self, data: dict) -> None:
        self.save_requested.emit(data)

    def _on_execute_cb(self, data: dict) -> None:
        self.execute_requested.emit(data)

    def _on_capture_cb(self) -> list:
        if self._capture_handler is not None:
            try:
                return self._capture_handler() or []
            except Exception as exc:
                _logger.error("capture handler failed: %s", exc)
        return []

    def _on_camera_feed_cb(self) -> None:
        pass

    # ── Public API ────────────────────────────────────────────────────

    def update_camera_feed(self, image) -> None:
        if self._editor is not None and image is not None:
            if hasattr(self._editor, "set_image"):
                self._editor.set_image(image)

    def update_contours(self, contours: list) -> None:
        if self._editor is None:
            return
        try:
            editor = self._editor.contourEditor.editor_with_rulers.editor
            if hasattr(editor, "set_contours"):
                editor.set_contours(contours)
        except AttributeError:
            pass
