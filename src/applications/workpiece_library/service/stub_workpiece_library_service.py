import logging
from typing import List, Optional

from src.applications.workpiece_library.domain.workpiece_schema import (
    WorkpieceSchema, WorkpieceFieldDescriptor, WorkpieceRecord,
)
from src.applications.workpiece_library.service.i_workpiece_library_service import IWorkpieceLibraryService

_logger = logging.getLogger(__name__)

_STUB_SCHEMA = WorkpieceSchema(
    id_key   = "workpieceId",
    name_key = "name",
    fields=[
        WorkpieceFieldDescriptor(key="workpieceId", label="ID"),
        WorkpieceFieldDescriptor(key="name",        label="Name"),
        WorkpieceFieldDescriptor(key="date",        label="Date"),
        WorkpieceFieldDescriptor(key="type",        label="Type",  detail_display=True, table_display=False),
    ],
)

_STUB_RECORDS = [
    WorkpieceRecord({"workpieceId": "WP-001", "name": "Cover Plate A", "date": "2026-01-10", "type": "Standard"}),
    WorkpieceRecord({"workpieceId": "WP-002", "name": "Frame B",       "date": "2026-01-15", "type": "Heavy"}),
    WorkpieceRecord({"workpieceId": "WP-003", "name": "Bracket C",     "date": "2026-02-03", "type": "Delicate"}),
]


class StubWorkpieceLibraryService(IWorkpieceLibraryService):

    def __init__(self, schema: WorkpieceSchema = _STUB_SCHEMA):
        self._schema  = schema
        self._records = list(_STUB_RECORDS)

    def get_schema(self) -> WorkpieceSchema:
        return self._schema

    def list_all(self) -> List[WorkpieceRecord]:
        _logger.info("Stub: list_all → %d records", len(self._records))
        return list(self._records)

    def delete(self, workpiece_id: str) -> tuple[bool, str]:
        before = len(self._records)
        self._records = [r for r in self._records
                         if r.get_id(self._schema.id_key) != workpiece_id]
        if len(self._records) < before:
            _logger.info("Stub: delete id=%s", workpiece_id)
            return True, f"Deleted {workpiece_id}"
        return False, f"Not found: {workpiece_id}"

    def get_thumbnail(self, workpiece_id: str) -> Optional[bytes]:
        _logger.info("Stub: get_thumbnail id=%s", workpiece_id)
        return None

    def update(self, storage_id: str, updates: dict) -> tuple[bool, str]:
        for i, r in enumerate(self._records):
            if r.get_id(self._schema.id_key) == storage_id:
                self._records[i] = r.with_updates(updates)
                _logger.info("Stub: update id=%s keys=%s", storage_id, list(updates.keys()))
                return True, "Updated"
        return False, f"Not found: {storage_id}"

    def load_raw(self, storage_id: str) -> Optional[dict]:
        _logger.info("Stub: load_raw id=%s", storage_id)
        return None
