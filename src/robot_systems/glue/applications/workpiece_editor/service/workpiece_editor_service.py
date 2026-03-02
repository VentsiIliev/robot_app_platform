import logging

from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config import WorkpieceFormSchema
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.segment_editor_config import SegmentEditorConfig
from src.robot_systems.glue.workpieces.service.i_workpiece_service import IWorkpieceService
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.handlers.SaveWorkpieceHandler import \
    SaveWorkpieceHandler
from src.robot_systems.glue.workpieces.model.glue_workpiece import GlueWorkpiece
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.adapters.workpiece_adapter import \
    WorkpieceAdapter
from contour_editor.persistence.data.editor_data_model import ContourEditorData

_logger = logging.getLogger(__name__)


class WorkpieceEditorService(IWorkpieceEditorService):

    def __init__(self,
                 vision_service,
                 workpiece_service: IWorkpieceService,
                 form_schema:       WorkpieceFormSchema,
                 segment_config:    SegmentEditorConfig):
        self._vision          = vision_service
        self._workpiece_service = workpiece_service
        self._form_schema     = form_schema
        self._segment_config  = segment_config

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
            form_data   = data.get("form_data", {})
            editor_data = data.get("editor_data")
            complete    = self._merge(form_data, editor_data) if editor_data else dict(form_data)

            required = self._form_schema.get_required_keys()
            is_valid, errors = SaveWorkpieceHandler.validate_form_data(complete, required)
            if not is_valid:
                msg = f"Validation failed: {', '.join(errors)}"
                _logger.warning("save_workpiece: %s", msg)
                return False, msg

            workpiece = GlueWorkpiece.from_dict(complete)
            return self._workpiece_service.save(workpiece)

        except Exception as exc:
            _logger.exception("save_workpiece failed")
            return False, str(exc)

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("execute_workpiece: %s", list(data.keys()))
        return True, "Workpiece executed"

    def _merge(self, form_data: dict, editor_data) -> dict:
        if not isinstance(editor_data, ContourEditorData):
            return dict(form_data)

        transformed = WorkpieceAdapter.to_workpiece_data(editor_data)
        merged      = {**transformed, **form_data}

        # normalise the material/type field using the schema's declared key
        mat_key = self._form_schema.material_type_key
        if mat_key:
            mat_val = (form_data.get(mat_key)
                       or form_data.get("glue_type")
                       or form_data.get("glueType"))
            if mat_val:
                merged[mat_key] = mat_val

        return merged
