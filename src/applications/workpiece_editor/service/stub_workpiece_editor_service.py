import logging
import copy
from contour_editor.persistence.data.editor_data_model import ContourEditorData
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.adapters.i_workpiece_data_adapter import IWorkpieceDataAdapter
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.applications.workpiece_editor.service.i_workpiece_path_executor import WorkpieceProcessAction

_logger = logging.getLogger(__name__)


class _StubWorkpieceDataAdapter(IWorkpieceDataAdapter):
    def from_workpiece(self, workpiece) -> ContourEditorData:
        return ContourEditorData()

    def to_workpiece_data(self, editor_data: ContourEditorData, default_settings=None) -> dict:
        return {"contour": [], "sprayPattern": {"Contour": [], "Fill": []}}

    def from_raw(self, raw: dict) -> ContourEditorData:
        return ContourEditorData()

    def print_summary(self, editor_data: ContourEditorData) -> None:
        return None


class StubWorkpieceEditorService(IWorkpieceEditorService):

    def __init__(self, form_schema: WorkpieceFormSchema, segment_config: SegmentEditorConfig):
        self._form_schema    = form_schema
        self._segment_config = segment_config
        self._adapter = _StubWorkpieceDataAdapter()

    def get_workpiece_data_adapter(self) -> IWorkpieceDataAdapter:
        return self._adapter

    def get_form_schema(self) -> WorkpieceFormSchema:
        return self._form_schema

    def get_segment_config(self) -> SegmentEditorConfig:
        return self._segment_config

    def get_contours(self) -> list:
        _logger.info("Stub: get_contours")
        return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: save_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece saved"

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: execute_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece executed"

    def get_process_actions(self) -> tuple[WorkpieceProcessAction, ...]:
        return (
            WorkpieceProcessAction(
                action_id="stub_process",
                label="Run Stub Process",
            ),
        )

    def execute_process_action(self, action_id: str) -> tuple[bool, str]:
        _logger.info("Stub: execute_process_action action_id=%s", action_id)
        return True, f"Stub: executed process action {action_id}"

    def can_import_dxf_test(self) -> bool:
        return False

    def prepare_dxf_test_raw_for_image(
        self,
        raw: dict,
        image_width: float,
        image_height: float,
    ) -> dict:
        _logger.info(
            "Stub: prepare_dxf_test_raw_for_image image_width=%s image_height=%s",
            image_width,
            image_height,
        )
        return copy.deepcopy(raw)

    def get_last_sampled_preview_paths(self) -> list:
        return []

    def get_last_raw_preview_paths(self) -> list:
        return []

    def get_last_prepared_preview_paths(self) -> list:
        return []

    def get_last_curve_preview_paths(self) -> list:
        return []

    def get_last_execution_preview_paths(self) -> list:
        return []

    def get_last_pivot_preview_paths(self) -> tuple[list[list[list[float]]], list[float] | None]:
        return [], None

    def get_last_pivot_motion_preview(self):
        return [], None

    def set_editing(self, storage_id) -> None:
        _logger.info("Stub: set_editing storage_id=%s", storage_id)

    def can_match_saved_workpieces(self) -> bool:
        return False

    def match_saved_workpieces(self, contour) -> tuple[bool, dict | None, str]:
        return False, None, "Matching is not available"
