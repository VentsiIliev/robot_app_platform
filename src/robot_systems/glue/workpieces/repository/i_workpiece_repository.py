from abc import ABC, abstractmethod
from typing import List, Optional


class IWorkpieceRepository(ABC):

    @abstractmethod
    def save(self, workpiece) -> str:
        """Persist workpiece. Returns the saved file path."""
        ...

    @abstractmethod
    def load(self, workpiece_id: str):
        """Load a single workpiece by its timestamp ID. Returns GlueWorkpiece or None."""
        ...

    @abstractmethod
    def list_all(self) -> List[dict]:
        """Return list of metadata dicts: {id, name, date, path}."""
        ...

    @abstractmethod
    def delete(self, workpiece_id: str) -> bool:
        """Delete workpiece folder by timestamp ID. Returns True on success."""
        ...