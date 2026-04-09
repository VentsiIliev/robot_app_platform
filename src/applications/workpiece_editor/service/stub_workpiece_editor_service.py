import logging
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig

_logger = logging.getLogger(__name__)


class StubWorkpieceEditorService(IWorkpieceEditorService):

    def __init__(self, form_schema: WorkpieceFormSchema, segment_config: SegmentEditorConfig):
        self._form_schema    = form_schema
        self._segment_config = segment_config

    def get_form_schema(self) -> WorkpieceFormSchema:
        return self._form_schema

    def get_segment_config(self) -> SegmentEditorConfig:
        return self._segment_config

    def get_contours(self) -> list:
        _logger.info("Stub: get_contours")
        return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: save_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece saved"

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: execute_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece executed"

    def execute_last_preview_paths(self, mode: str = "continuous") -> tuple[bool, str]:
        _logger.info("Stub: execute_last_preview_paths mode=%s", mode)
        return True, f"Stub: executed preview paths in {mode} mode"

    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]:
        return [], None

    def get_last_pivot_motion_preview(self):
        return [], None

    def set_editing(self, storage_id) -> None:
        _logger.info("Stub: set_editing storage_id=%s", storage_id)
