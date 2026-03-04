import json
import logging
from typing import List, Optional, Callable

from src.applications.workpiece_library.domain.workpiece_schema import (
    WorkpieceSchema, WorkpieceFieldDescriptor, WorkpieceRecord,
)
from src.applications.workpiece_library.service.i_workpiece_library_service import IWorkpieceLibraryService
from src.robot_systems.glue.domain.workpieces.model.glue_workpiece_filed import GlueWorkpieceField
from src.robot_systems.glue.domain.workpieces.service.i_workpiece_service import IWorkpieceService

_logger = logging.getLogger(__name__)

F = GlueWorkpieceField

def build_glue_workpiece_library_schema(glue_types: List[str]) -> WorkpieceSchema:
    return WorkpieceSchema(
        id_key   = "id",
        name_key = F.NAME.value,
        fields=[
            WorkpieceFieldDescriptor(key=F.WORKPIECE_ID.value,  label="ID",          table_display=True,  detail_display=True,  editable=True,  widget="text"),
            WorkpieceFieldDescriptor(key=F.NAME.value,          label="Name",        table_display=True,  detail_display=True,  editable=True,  widget="text"),
            WorkpieceFieldDescriptor(key="date",                label="Date",        table_display=True,  detail_display=True,  editable=False),
            WorkpieceFieldDescriptor(key=F.GLUE_TYPE.value,     label="Glue Type",   table_display=True,  detail_display=True,  editable=True,  widget="combo", options=glue_types),
            WorkpieceFieldDescriptor(key=F.HEIGHT.value,        label="Height (mm)", table_display=False, detail_display=True,  editable=True,  widget="text"),
            WorkpieceFieldDescriptor(key=F.GRIPPER_ID.value,    label="Gripper",     table_display=False, detail_display=True,  editable=False),
            WorkpieceFieldDescriptor(key=F.DESCRIPTION.value,   label="Description", table_display=False, detail_display=True,  editable=True,  widget="text"),
        ],
    )


class GlueWorkpieceLibraryService(IWorkpieceLibraryService):

    def __init__(self, workpiece_service: IWorkpieceService, glue_types_fn: Callable[[], List[str]]):
        self._service       = workpiece_service
        self._glue_types_fn = glue_types_fn   # called fresh each time get_schema() is invoked

    def get_schema(self) -> WorkpieceSchema:
        return build_glue_workpiece_library_schema(self._glue_types_fn())


    def list_all(self) -> List[WorkpieceRecord]:
        records = []
        for meta in self._service.list_all():
            data = {
                "id": meta.get("id", ""),  # timestamp — used for delete
                F.NAME.value: meta.get("name", ""),
                "date": meta.get("date", ""),
                F.WORKPIECE_ID.value: "",  # populated from JSON below
            }
            path = meta.get("path")
            if path:
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        raw = json.load(fh)
                    data[F.WORKPIECE_ID.value] = raw.get(F.WORKPIECE_ID.value, "")
                    data[F.NAME.value] = raw.get(F.NAME.value, data[F.NAME.value])
                    data[F.GLUE_TYPE.value] = raw.get(F.GLUE_TYPE.value, "")
                    data[F.HEIGHT.value] = raw.get(F.HEIGHT.value, "")
                    data[F.GRIPPER_ID.value] = raw.get(F.GRIPPER_ID.value, "")
                    data[F.DESCRIPTION.value] = raw.get(F.DESCRIPTION.value, "")
                except Exception as exc:
                    _logger.warning("Could not enrich workpiece %s: %s", meta.get("id"), exc)
            records.append(WorkpieceRecord(data))
        return records

    def delete(self, workpiece_id: str) -> tuple[bool, str]:
        return self._service.delete(workpiece_id)

    def get_thumbnail(self, workpiece_id: str) -> Optional[bytes]:
        return self._service.get_thumbnail_bytes(workpiece_id)

    def update(self, storage_id: str, updates: dict) -> tuple[bool, str]:
        """Patch only the editable fields in the stored JSON file."""
        meta_list = self._service.list_all()
        meta = next((m for m in meta_list if m.get("id") == storage_id), None)
        if meta is None:
            return False, f"Workpiece '{storage_id}' not found"
        path = meta.get("path")
        if not path:
            return False, "No file path for workpiece"
        try:
            import json
            with open(path, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            raw.update(updates)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(raw, fh, indent=2, default=str)
            _logger.info("Updated workpiece %s: %s", storage_id, list(updates.keys()))
            return True, "Workpiece updated"
        except Exception as exc:
            _logger.exception("Failed to update workpiece %s", storage_id)
            return False, str(exc)

    def load_raw(self, storage_id: str) -> Optional[dict]:
        import json
        meta_list = self._service.list_all()
        meta = next((m for m in meta_list if m.get("id") == storage_id), None)
        if meta is None:
            return None
        path = meta.get("path")
        if not path:
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception as exc:
            _logger.exception("load_raw failed for %s", storage_id)
            return None

