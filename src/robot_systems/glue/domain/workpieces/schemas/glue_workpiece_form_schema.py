import os
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import (
    WorkpieceFormSchema, WorkpieceFormFieldSpec, FieldIcon,
)
from src.robot_systems.glue.domain.workpieces.model.glue_workpiece_filed import GlueWorkpieceField
from src.robot_systems.glue.tools.enums.Gripper import Gripper

_ICONS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__),
    '../../..', '..', '..', 'applications',
    'workpiece_editor', 'editor_core', 'assets', 'icons',
))

_COLOR = "#905BA9"
WORKPIECE_ID_ICON   = FieldIcon.from_qta("fa5s.barcode",        color=_COLOR)
WORKPIECE_NAME_ICON = FieldIcon.from_qta("fa5s.tag",            color=_COLOR)
DESCRIPTION_ICON    = FieldIcon.from_qta("fa5s.align-left",     color=_COLOR)
HEIGHT_ICON         = FieldIcon.from_qta("fa5s.ruler-vertical", color=_COLOR)
GLUE_QTY_ICON       = FieldIcon.from_qta("fa5s.weight-hanging", color=_COLOR)
GRIPPER_ID_ICON     = FieldIcon.from_qta("mdi.robot-industrial",          color=_COLOR)
GLUE_TYPE_ICON      = FieldIcon.from_qta("fa5s.eye-dropper",           color=_COLOR)


def _path(name: str) -> FieldIcon:
    p = os.path.join(_ICONS_DIR, f"{name}.png")
    return FieldIcon.from_path(p) if os.path.exists(p) else FieldIcon.none()

def build_glue_workpiece_form_schema(glue_types=None) -> WorkpieceFormSchema:
    glue_types = glue_types or ["Type A", "Type B"]
    return WorkpieceFormSchema(
        id_key    = GlueWorkpieceField.WORKPIECE_ID.value,
        combo_key = GlueWorkpieceField.GLUE_TYPE.value,
        fields=[
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.WORKPIECE_ID.value, label="Workpiece ID", field_type="text",     mandatory=True,  icon=WORKPIECE_ID_ICON),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.NAME.value,         label="Name",          field_type="text",     mandatory=False, icon=WORKPIECE_NAME_ICON),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.DESCRIPTION.value,  label="Description",   field_type="text",     mandatory=False, icon=DESCRIPTION_ICON),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.HEIGHT.value,       label="Height",        field_type="text",     mandatory=True,  placeholder="mm",    icon=HEIGHT_ICON),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.GLUE_QTY.value,     label="Glue Qty",      field_type="text",     mandatory=False, placeholder="g /m²", icon=GLUE_QTY_ICON),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.GRIPPER_ID.value,   label="Gripper",       field_type="dropdown", mandatory=False, options=[Gripper.SINGLE, Gripper.DOUBLE], icon=GRIPPER_ID_ICON),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.GLUE_TYPE.value,    label="Glue Type",     field_type="dropdown", mandatory=True,  options=glue_types,  icon=GLUE_TYPE_ICON),
        ],
    )
