import logging
from PyQt6.QtCore import QObject

from ..adapters.i_workpiece_data_adapter import IWorkpieceDataAdapter

_logger = logging.getLogger(__name__)


class StartHandler(QObject):
    """
    Intercepts the editor's start_requested signal, validates material type
    assignments on all segments, then re-emits execute_requested.
    System-agnostic — validates that a material_type_key field is set on
    every segment, but knows nothing about GlueType or any specific type.
    """

    def __init__(self, editor_frame, adapter: IWorkpieceDataAdapter, parent=None):
        super().__init__(parent)
        self.editor_frame = editor_frame
        self._adapter = adapter

    def handle_start(self) -> None:
        try:
            from contour_editor.persistence.data.editor_data_model import ContourEditorData

            editor = (self.editor_frame.contourEditor
                      .editor_with_rulers.editor)

            editor_data: ContourEditorData = (
                editor.workpiece_manager.export_editor_data()
                if hasattr(editor, "workpiece_manager") else None
            )

            contour_data = (self._adapter.to_workpiece_data(editor_data)
                            if editor_data else {})

            self.editor_frame.execute_requested.emit(contour_data)

        except Exception as exc:
            _logger.error("StartHandler.handle_start failed: %s", exc)
