import os
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.workpiece_form_schema import (
    WorkpieceFormSchema, WorkpieceFormFieldSpec,
)
from src.robot_systems.glue.workpieces.model.glue_workpiece_filed import GlueWorkpieceField
from src.robot_systems.glue.tools.enums.Gripper import Gripper


def _icon(name: str) -> str:
    base = os.path.join(os.path.dirname(__file__), '..', 'applications', 'workpiece_editor',
                        'workpiece_editor', 'assets', 'icons')
    p = os.path.join(base, f"{name}.png")
    return p if os.path.exists(p) else ""


def build_glue_workpiece_form_schema(glue_types=None) -> WorkpieceFormSchema:
    glue_types = glue_types or ["Type A", "Type B"]
    return WorkpieceFormSchema(
        id_key=GlueWorkpieceField.WORKPIECE_ID.value,
        fields=[
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.WORKPIECE_ID.value, label="Workpiece ID",  field_type="text",     mandatory=True,  icon_path=_icon("WOPIECE_ID_ICON_2")),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.NAME.value,         label="Name",           field_type="text",     mandatory=False, icon_path=_icon("WORKPIECE_NAME_ICON")),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.DESCRIPTION.value,  label="Description",    field_type="text",     mandatory=False, icon_path=_icon("DESCRIPTION_WORKPIECE_BUTTON_SQUARE")),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.HEIGHT.value,       label="Height",         field_type="text",     mandatory=True,  placeholder="mm"),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.GLUE_QTY.value,     label="Glue Qty",       field_type="text",     mandatory=False, placeholder="g /m²", icon_path=_icon("glue_qty")),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.GRIPPER_ID.value,   label="Gripper",        field_type="dropdown", mandatory=False, options=[Gripper.SINGLE, Gripper.DOUBLE], icon_path=_icon("GRIPPER_ID_ICON")),
            WorkpieceFormFieldSpec(key=GlueWorkpieceField.GLUE_TYPE.value,    label="Glue Type",      field_type="dropdown", mandatory=True,  options=glue_types, icon_path=_icon("GLUE_TYPE_ICON")),
        ],
    )