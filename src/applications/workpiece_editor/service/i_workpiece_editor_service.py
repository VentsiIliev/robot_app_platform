from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig


class IWorkpieceEditorService(ABC):

    @abstractmethod
    def get_form_schema(self) -> WorkpieceFormSchema: ...

    @abstractmethod
    def get_segment_config(self) -> SegmentEditorConfig: ...

    @abstractmethod
    def get_contours(self) -> list: ...

    @abstractmethod
    def save_workpiece(self, data: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def execute_workpiece(self, data: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def get_last_interpolation_preview_contours(self) -> list: ...

    @abstractmethod
    def get_last_interpolation_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_original_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_pre_smoothed_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_linear_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_execution_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]: ...

    @abstractmethod
    def get_last_pivot_motion_preview(self) -> tuple[list[list[np.ndarray]], list[float] | None]: ...

    @abstractmethod
    def execute_last_preview_paths(self, mode: str = "continuous") -> tuple[bool, str]: ...

    @abstractmethod
    def set_editing(self, storage_id: Optional[str]) -> None:
        """Pass storage_id to edit an existing workpiece on the next save, or None for new."""
        ...
