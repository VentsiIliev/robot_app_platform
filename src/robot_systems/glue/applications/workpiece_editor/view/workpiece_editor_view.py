import logging

from PyQt6.QtWidgets import QVBoxLayout, QLabel
from PyQt6.QtCore import pyqtSignal
from contour_editor import BezierSegmentManager

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import (
    WorkpieceFormSchema, WorkpieceFormFactory, SegmentEditorConfig,
)
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor import WorkpieceEditorBuilder
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.virtual_keyboard_widget_factory import \
    VirtualKeyboardWidgetFactory
from src.applications.base.i_application_view import IApplicationView

_logger = logging.getLogger(__name__)


class WorkpieceEditorView(IApplicationView):

    save_requested    = pyqtSignal(dict)
    execute_requested = pyqtSignal(dict)

    def __init__(self, schema: WorkpieceFormSchema, segment_config: SegmentEditorConfig, parent=None):
        self._schema          = schema
        self._segment_config  = segment_config
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
        pass

    def _build_editor(self):
        return (
            WorkpieceEditorBuilder()
            .with_segment_manager(BezierSegmentManager)
            .with_settings(
                self._segment_config.settings_config,
                self._segment_config.settings_provider,
            )
            .with_form(WorkpieceFormFactory(schema=self._schema))
            .with_widgets(VirtualKeyboardWidgetFactory())
            .on_save(self._on_save_cb)
            .on_capture(self._on_capture_cb)
            .on_execute(self._on_execute_cb)
            .on_update_camera_feed(self._on_camera_feed_cb)
            .build()
        )

    def set_capture_handler(self, handler) -> None:
        self._capture_handler = handler

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

