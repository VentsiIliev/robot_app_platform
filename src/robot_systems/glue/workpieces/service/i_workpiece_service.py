from abc import ABC, abstractmethod
from typing import List, Optional


class IWorkpieceService(ABC):

    @abstractmethod
    def save(self, workpiece) -> tuple[bool, str]: ...

    @abstractmethod
    def load(self, workpiece_id: str): ...

    @abstractmethod
    def list_all(self) -> List[dict]: ...

    @abstractmethod
    def delete(self, workpiece_id: str) -> tuple[bool, str]: ...