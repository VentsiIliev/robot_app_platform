import logging
from typing import List, Optional, Callable

from src.applications.workpiece_editor.editor_core import WorkpieceField
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.robot_systems.glue.domain.workpieces.repository.i_workpiece_repository import IWorkpieceRepository

from src.robot_systems.glue.domain.workpieces.service.i_workpiece_service import IWorkpieceService

_logger = logging.getLogger(__name__)


class WorkpieceService(IWorkpieceService):

    def __init__(
            self,
            repository: IWorkpieceRepository,
            tool_provider: Optional[Callable[[], List[ToolDefinition]]] = None,
    ):
        self._repo = repository
        self._tool_provider = tool_provider

    def save(self, workpiece) -> tuple[bool, str]:
        _logger.info("WorkpieceService.save: %s", workpiece)
        tools = self._tool_provider()
        # resolve tools id by tool name
        wp_gripper = workpiece.get(WorkpieceField.GRIPPER_ID.value)
        tool_found= False
        for tool in tools:
            if wp_gripper == tool.name:
                workpiece[WorkpieceField.GRIPPER_ID.value] = tool.id
                tool_found = True
                break

        if not tool_found:
            _logger.error("WorkpieceService.save: tool not found for %s", wp_gripper)
            return False, f"Tool not found for {wp_gripper}"

        _logger.info("WorkpieceService.save: tools: %s", tools)
        try:
            path = self._repo.save(workpiece)
            return True, path
        except Exception as exc:
            _logger.exception("WorkpieceService.save failed")
            return False, str(exc)

    def load(self, workpiece_id: str):
        try:
            return self._repo.load(workpiece_id)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.exception("WorkpieceService.load failed")
            return None

    def list_all(self) -> List[dict]:
        try:
            return self._repo.list_all()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.exception("WorkpieceService.list_all failed")
            return []

    def delete(self, workpiece_id: str) -> tuple[bool, str]:
        try:
            ok = self._repo.delete(workpiece_id)
            return (True, "Deleted") if ok else (False, f"Workpiece '{workpiece_id}' not found")
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.exception("WorkpieceService.delete failed")
            return False, str(exc)

    def get_thumbnail_bytes(self, workpiece_id: str) -> Optional[bytes]:
        try:
            return self._repo.get_thumbnail_bytes(workpiece_id)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.exception("get_thumbnail_bytes failed for %s", workpiece_id)
            return None

    def workpiece_id_exists(self, workpiece_id: str) -> bool:
        try:
            return self._repo.workpiece_id_exists(workpiece_id)
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.exception("workpiece_id_exists failed for %s", workpiece_id)
            return False

    def update(self, storage_id: str, data: dict) -> tuple[bool, str]:
        try:
            path = self._repo.update(storage_id, data)
            return True, path
        except Exception as exc:
            import traceback
            traceback.print_exc()
            _logger.exception("WorkpieceService.update failed for %s", storage_id)
            return False, str(exc)