import logging
from typing import List, Optional

from src.robot_systems.glue.domain.workpieces.repository.i_workpiece_repository import IWorkpieceRepository

from src.robot_systems.glue.domain.workpieces.service.i_workpiece_service import IWorkpieceService

_logger = logging.getLogger(__name__)


class WorkpieceService(IWorkpieceService):

    def __init__(self, repository: IWorkpieceRepository):
        self._repo = repository

    def save(self, workpiece) -> tuple[bool, str]:
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
            _logger.exception("WorkpieceService.load failed")
            return None

    def list_all(self) -> List[dict]:
        try:
            return self._repo.list_all()
        except Exception as exc:
            _logger.exception("WorkpieceService.list_all failed")
            return []

    def delete(self, workpiece_id: str) -> tuple[bool, str]:
        try:
            ok = self._repo.delete(workpiece_id)
            return (True, "Deleted") if ok else (False, f"Workpiece '{workpiece_id}' not found")
        except Exception as exc:
            _logger.exception("WorkpieceService.delete failed")
            return False, str(exc)

    def get_thumbnail_bytes(self, workpiece_id: str) -> Optional[bytes]:
        try:
            return self._repo.get_thumbnail_bytes(workpiece_id)
        except Exception as exc:
            _logger.exception("get_thumbnail_bytes failed for %s", workpiece_id)
            return None

    def workpiece_id_exists(self, workpiece_id: str) -> bool:
        try:
            return self._repo.workpiece_id_exists(workpiece_id)
        except Exception as exc:
            _logger.exception("workpiece_id_exists failed for %s", workpiece_id)
            return False

    def update(self, storage_id: str, data: dict) -> tuple[bool, str]:
        try:
            path = self._repo.update(storage_id, data)
            return True, path
        except Exception as exc:
            _logger.exception("WorkpieceService.update failed for %s", storage_id)
            return False, str(exc)