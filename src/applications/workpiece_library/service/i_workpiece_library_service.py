from abc import ABC, abstractmethod
from typing import List, Optional

from src.applications.workpiece_library.domain.workpiece_schema import WorkpieceSchema, WorkpieceRecord


class IWorkpieceLibraryService(ABC):

    @abstractmethod
    def get_schema(self) -> WorkpieceSchema: ...

    @abstractmethod
    def list_all(self) -> List[WorkpieceRecord]: ...

    @abstractmethod
    def update(self, storage_id: str, updates: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def delete(self, workpiece_id: str) -> tuple[bool, str]: ...

    @abstractmethod
    def get_thumbnail(self, workpiece_id: str) -> Optional[bytes]: ...

    @abstractmethod
    def load_raw(self, storage_id: str) -> Optional[dict]:
        """Return the raw stored dict for a workpiece by its storage (timestamp) ID."""
        ...