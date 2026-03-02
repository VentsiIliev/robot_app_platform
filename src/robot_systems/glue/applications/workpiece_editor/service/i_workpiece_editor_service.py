from abc import ABC, abstractmethod
from typing import List


class IWorkpieceEditorService(ABC):

    @abstractmethod
    def get_glue_types(self) -> List[str]: ...

    @abstractmethod
    def get_contours(self) -> list: ...

    @abstractmethod
    def save_workpiece(self, data: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def execute_workpiece(self, data: dict) -> tuple[bool, str]: ...