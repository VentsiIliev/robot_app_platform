from abc import ABC, abstractmethod
from typing import Optional

from src.applications.workpiece_editor.editor_core.adapters.i_workpiece_data_adapter import IWorkpieceDataAdapter
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.applications.workpiece_editor.service.i_workpiece_path_executor import WorkpieceProcessAction


class IWorkpieceEditorService(ABC):

    @abstractmethod
    def get_workpiece_data_adapter(self) -> IWorkpieceDataAdapter: ...

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
    def get_last_sampled_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_raw_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_prepared_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_curve_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_execution_preview_paths(self) -> list: ...

    @abstractmethod
    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]: ...

    @abstractmethod
    def get_last_pivot_motion_preview(self) -> tuple[list, list[float] | None]: ...

    @abstractmethod
    def get_process_actions(self) -> tuple[WorkpieceProcessAction, ...]: ...

    @abstractmethod
    def execute_process_action(self, action_id: str) -> tuple[bool, str]: ...

    @abstractmethod
    def can_import_dxf_test(self) -> bool: ...

    @abstractmethod
    def prepare_dxf_test_raw_for_image(
        self,
        raw: dict,
        image_width: float,
        image_height: float,
    ) -> dict: ...

    @abstractmethod
    def set_editing(self, storage_id: Optional[str]) -> None:
        """Pass storage_id to edit an existing workpiece on the next save, or None for new."""
        ...

    @abstractmethod
    def can_match_saved_workpieces(self) -> bool: ...

    @abstractmethod
    def match_saved_workpieces(self, contour) -> tuple[bool, dict | None, str]: ...
