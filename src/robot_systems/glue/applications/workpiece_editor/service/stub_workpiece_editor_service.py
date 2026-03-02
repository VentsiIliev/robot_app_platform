import logging
from typing import List
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService

_logger = logging.getLogger(__name__)


class StubWorkpieceEditorService(IWorkpieceEditorService):

    def get_glue_types(self) -> List[str]:
        return ["Type A", "Type B", "Type C"]

    def get_contours(self) -> list:
        _logger.info("Stub: get_contours")
        return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: save_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece saved"

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: execute_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece executed"