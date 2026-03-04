from typing import List, Optional

from src.applications.base.i_application_model import IApplicationModel
from src.applications.workpiece_library.domain.workpiece_schema import WorkpieceSchema, WorkpieceRecord
from src.applications.workpiece_library.service.i_workpiece_library_service import IWorkpieceLibraryService


class WorkpieceLibraryModel(IApplicationModel):

    def __init__(self, service: IWorkpieceLibraryService):
        self._service = service
        self._records: List[WorkpieceRecord] = []
        self._schema:  WorkpieceSchema       = service.get_schema()

    @property
    def schema(self) -> WorkpieceSchema:
        return self._schema

    def load(self) -> List[WorkpieceRecord]:
        self._records = self._service.list_all()
        return self._records

    def save(self, *args, **kwargs) -> None:
        pass

    def get_all(self) -> List[WorkpieceRecord]:
        return list(self._records)

    def delete(self, workpiece_id: str) -> tuple[bool, str]:
        ok, msg = self._service.delete(workpiece_id)
        if ok:
            self._records = self._service.list_all()
        return ok, msg

    def get_thumbnail(self, workpiece_id: str) -> Optional[bytes]:
        return self._service.get_thumbnail(workpiece_id)

    def update(self, storage_id: str, updates: dict) -> tuple[bool, str]:
        ok, msg = self._service.update(storage_id, updates)
        if ok:
            self._records = self._service.list_all()
        return ok, msg

    def load_raw(self, storage_id: str) -> Optional[dict]:
        return self._service.load_raw(storage_id)

    def get_schema(self) -> WorkpieceSchema:
        return self._service.get_schema()  # calls _glue_types_fn() + _tools_fn() fresh
