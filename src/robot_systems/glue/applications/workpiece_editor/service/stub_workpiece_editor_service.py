import logging
from typing import List
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.workpiece_form_schema import WorkpieceFormSchema, WorkpieceFormFieldSpec
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.segment_editor_config import SegmentEditorConfig

_logger = logging.getLogger(__name__)

_STUB_SCHEMA = WorkpieceFormSchema(
    id_key="workpieceId",
    material_type_key="glueType",
    fields=[
        WorkpieceFormFieldSpec(key="workpieceId", label="ID",        field_type="text",     mandatory=True),
        WorkpieceFormFieldSpec(key="name",         label="Name",      field_type="text",     mandatory=False),
        WorkpieceFormFieldSpec(key="height",       label="Height",    field_type="text",     mandatory=True),
        WorkpieceFormFieldSpec(key="glueType",     label="Glue Type", field_type="dropdown", mandatory=True,
                               options=["Type A", "Type B"]),
    ],
)


def _build_stub_segment_config() -> SegmentEditorConfig:
    from contour_editor import SettingsConfig, SettingsGroup
    from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.segment_settings_provider import \
        SegmentSettingsProvider
    provider = SegmentSettingsProvider(material_types=["Type A", "Type B"])
    config   = SettingsConfig(
        default_settings=provider.get_default_values(),
        groups=[SettingsGroup("Settings", list(provider.get_default_values().keys()))],
        combo_field_key=provider.get_material_type_key(),
    )
    return SegmentEditorConfig(settings_config=config, settings_provider=provider)


class StubWorkpieceEditorService(IWorkpieceEditorService):

    def get_form_schema(self) -> WorkpieceFormSchema:
        return _STUB_SCHEMA

    def get_segment_config(self) -> SegmentEditorConfig:
        return _build_stub_segment_config()

    def get_contours(self) -> list:
        _logger.info("Stub: get_contours")
        return []

    def save_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: save_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece saved"

    def execute_workpiece(self, data: dict) -> tuple[bool, str]:
        _logger.info("Stub: execute_workpiece keys=%s", list(data.keys()))
        return True, "Stub: workpiece executed"
