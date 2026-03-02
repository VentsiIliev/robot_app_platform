from abc import ABC, abstractmethod
from typing import List
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.workpiece_form_schema import WorkpieceFormSchema


class IWorkpieceEditorService(ABC):

    @abstractmethod
    def get_form_schema(self) -> WorkpieceFormSchema: ...

    @abstractmethod
    def get_glue_types(self) -> List[str]: ...

    @abstractmethod
    def get_contours(self) -> list: ...

    @abstractmethod
    def save_workpiece(self, data: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def execute_workpiece(self, data: dict) -> tuple[bool, str]: ...
