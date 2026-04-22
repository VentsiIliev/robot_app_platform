import logging
from typing import List, Optional

_logger = logging.getLogger(__name__)


class PaintWorkpieceService:
    def __init__(self, repository):
        self._repo = repository

    def save(self, workpiece: dict) -> tuple[bool, str]:
        try:
            return True, self._repo.save(workpiece)
        except Exception as exc:
            _logger.exception("PaintWorkpieceService.save failed")
            return False, str(exc)

    def list_all(self) -> List[dict]:
        try:
            return self._repo.list_all()
        except Exception:
            _logger.exception("PaintWorkpieceService.list_all failed")
            return []

    def delete(self, storage_id: str) -> tuple[bool, str]:
        try:
            ok = self._repo.delete(storage_id)
            return (True, "Deleted") if ok else (False, f"Workpiece '{storage_id}' not found")
        except Exception as exc:
            _logger.exception("PaintWorkpieceService.delete failed")
            return False, str(exc)

    def get_thumbnail_bytes(self, storage_id: str) -> Optional[bytes]:
        try:
            return self._repo.get_thumbnail_bytes(storage_id)
        except Exception:
            _logger.exception("PaintWorkpieceService.get_thumbnail_bytes failed")
            return None

    def workpiece_id_exists(self, workpiece_id: str) -> bool:
        try:
            return self._repo.workpiece_id_exists(workpiece_id)
        except Exception:
            _logger.exception("PaintWorkpieceService.workpiece_id_exists failed")
            return False

    def update(self, storage_id: str, data: dict) -> tuple[bool, str]:
        try:
            return True, self._repo.update(storage_id, data)
        except Exception as exc:
            _logger.exception("PaintWorkpieceService.update failed")
            return False, str(exc)

    def load_raw(self, storage_id: str) -> Optional[dict]:
        try:
            return self._repo.load_raw(storage_id)
        except Exception:
            _logger.exception("PaintWorkpieceService.load_raw failed")
            return None
