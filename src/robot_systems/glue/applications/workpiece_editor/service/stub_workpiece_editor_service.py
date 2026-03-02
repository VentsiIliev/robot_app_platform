import logging
from typing import List
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.workpiece_form_schema import WorkpieceFormSchema, WorkpieceFormFieldSpec
_logger = logging.getLogger(__name__)

_STUB_SCHEMA = WorkpieceFormSchema(
    id_key="workpieceId",
    fields=[
        WorkpieceFormFieldSpec(key="workpieceId", label="ID",          field_type="text",     mandatory=True),
        WorkpieceFormFieldSpec(key="name",         label="Name",        field_type="text",     mandatory=False),
        WorkpieceFormFieldSpec(key="height",       label="Height",      field_type="text",     mandatory=True),
        WorkpieceFormFieldSpec(key="glueType",     label="Glue Type",   field_type="dropdown", mandatory=True,
                               options=["Type A", "Type B"]),
    ],
)

class StubWorkpieceEditorService(IWorkpieceEditorService):

    def get_glue_types(self) -> List[str]:
        return ["Type A", "Type B", "Type C"]

    def get_contours(self) -> list:
        _logger.info("Stub: get_contours")
        return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: save_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece saved"

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: execute_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece executed"

    def get_form_schema(self) -> WorkpieceFormSchema:
        return _STUB_SCHEMA