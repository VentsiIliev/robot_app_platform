import logging
from enum import Enum
from typing import List

from src.robot_systems.glue.workpieces.service.i_workpiece_service import IWorkpieceService
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService
from src.engine.vision.i_vision_service import IVisionService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.handlers.SaveWorkpieceHandler import \
    SaveWorkpieceHandler
from src.robot_systems.glue.workpieces.model.glue_workpiece import GlueWorkpiece
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.adapters.workpiece_adapter import \
    WorkpieceAdapter
from contour_editor.persistence.data.editor_data_model import ContourEditorData
from src.robot_systems.glue.workpieces.model.glue_workpiece_filed import GlueWorkpieceField

_logger = logging.getLogger(__name__)


class WorkpieceEditorService(IWorkpieceEditorService):

    def __init__(self,
                 vision_service: IVisionService,
                 workpiece_service: IWorkpieceService,
                 settings_service: ISettingsService,
                 catalog_key: Enum):
        self._vision            = vision_service
        self._workpiece_service = workpiece_service
        self._settings          = settings_service
        self._catalog_key       = catalog_key

    def get_glue_types(self) -> List[str]:
        try:
            catalog = self._settings.get(self._catalog_key)
            return catalog.get_all_names()
        except Exception as exc:
            _logger.error("get_glue_types failed: %s", exc)
            return []

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

            is_valid, errors = SaveWorkpieceHandler.validate_form_data(complete)
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

    @staticmethod
    def _merge(form_data: dict, editor_data) -> dict:


        if not isinstance(editor_data, ContourEditorData):
            return dict(form_data)

        transformed = WorkpieceAdapter.to_workpiece_data(editor_data)
        merged      = {**transformed, **form_data}

        glue_type = form_data.get("glue_type") or form_data.get("glueType")
        if glue_type:
            merged[GlueWorkpieceField.GLUE_TYPE.value] = glue_type

        return merged
