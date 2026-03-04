import logging
from typing import Callable
import numpy as np
from src.applications.workpiece_editor.editor_core.config import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.config.segment_editor_config import SegmentEditorConfig
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.editor_core.handlers.SaveWorkpieceHandler import SaveWorkpieceHandler
from src.applications.workpiece_editor.editor_core.adapters.workpiece_adapter import WorkpieceAdapter
from contour_editor.persistence.data.editor_data_model import ContourEditorData

_logger = logging.getLogger(__name__)

def _has_valid_contour(contour) -> bool:
    if contour is None:
        return False
    if isinstance(contour, np.ndarray):
        return int(contour.size) >= 3
    if isinstance(contour, list):
        return len(contour) >= 3
    return False


class WorkpieceEditorService(IWorkpieceEditorService):

    def __init__(self,
                 vision_service,
                 save_fn:        Callable[[dict], tuple[bool, str]],
                 update_fn:      Callable[[str, dict], tuple[bool, str]],
                 form_schema:    WorkpieceFormSchema,
                 segment_config: SegmentEditorConfig,
                 id_exists_fn:   Callable[[str], bool] = None):
        self._vision              = vision_service
        self._save_fn             = save_fn
        self._update_fn           = update_fn
        self._id_exists_fn        = id_exists_fn
        self._form_schema         = form_schema
        self._segment_config      = segment_config
        self._editing_storage_id  = None   # set → edit mode; None → create mode

    def set_editing(self, storage_id) -> None:
        self._editing_storage_id = storage_id
        _logger.debug("WorkpieceEditorService: editing_storage_id=%s", storage_id)


    def get_form_schema(self) -> WorkpieceFormSchema:
        return self._form_schema

    def get_segment_config(self) -> SegmentEditorConfig:
        return self._segment_config

    def get_contours(self) -> list:
        if self._vision is None:
            _logger.warning("get_contours: no vision service")
            return []
        try:
            return self._vision.get_latest_contours()
        except Exception as exc:
            _logger.error("get_contours failed: %s", exc)
            return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        try:
            form_data = data.get("form_data", {})
            editor_data = data.get("editor_data")
            complete = self._merge(form_data, editor_data) if editor_data else dict(form_data)
            print(f"[save_workpiece] complete: {complete}]")
            required = self._form_schema.get_required_keys()
            is_valid, errors = SaveWorkpieceHandler.validate_form_data(complete, required)
            if not is_valid:
                return False, f"Validation failed: {', '.join(errors)}"

            # ── Validate main contour ─────────────────────────────────────────────
            if not _has_valid_contour(complete.get("contour")):
                return False, (
                    "No main workpiece contour found.\n"
                    "Use the camera capture button to define the workpiece boundary first."
                )

            if self._editing_storage_id is not None:
                storage_id = self._editing_storage_id
                self._editing_storage_id = None
                return self._update_fn(storage_id, complete)
            else:
                if self._id_exists_fn is not None:
                    wp_id = str(complete.get("workpieceId", "")).strip()
                    if wp_id and self._id_exists_fn(wp_id):
                        return False, f"A workpiece with ID '{wp_id}' already exists"
                return self._save_fn(complete)

        except Exception as exc:
            _logger.exception("save_workpiece failed")
            return False, str(exc)

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("execute_workpiece keys=%s", list(data.keys()))
        return True, "Workpiece executed"

    def _merge(self, form_data: dict, editor_data) -> dict:
        if not isinstance(editor_data, ContourEditorData):
            return dict(form_data)
        merged = {**WorkpieceAdapter.to_workpiece_data(editor_data), **form_data}
        combo_key = self._form_schema.combo_key  # ← was material_type_key
        if combo_key:
            val = form_data.get(combo_key) or form_data.get("glue_type") or form_data.get("glueType")
            if val:
                merged[combo_key] = val
        return merged


