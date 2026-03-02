import os

from src.robot_systems.glue.workpieces.model.glue_workpiece_filed import GlueWorkpieceField
from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.ui.CreateWorkpieceForm import GenericFormConfig, \
    FormFieldConfig



from src.robot_systems.glue.tools.enums.Gripper import Gripper


def get_icon_path(icon_name):
    base_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'icons')
    icon_file = f"{icon_name}.png"
    full_path = os.path.join(base_path, icon_file)
    return full_path if os.path.exists(full_path) else ""


def get_contour_icon_path(icon_name):
    base_path = os.path.join(os.path.dirname(__file__), '..', '..', 'contour_editor', 'assets', 'icons')
    icon_file = f"{icon_name}.png"
    full_path = os.path.join(base_path, icon_file)
    return full_path if os.path.exists(full_path) else ""



def create_workpiece_form_config(glue_types=None) -> GenericFormConfig:
    print(f"Creating config new")
    if glue_types is None or (isinstance(glue_types, list) and len(glue_types) == 0):
        glue_types = ["Type A", "Type B", "Type C"]

    fields = [
        FormFieldConfig(
            field_id=GlueWorkpieceField.WORKPIECE_ID.value,
            field_type="text",
            label=GlueWorkpieceField.WORKPIECE_ID.getAsLabel(),
            icon_path=get_icon_path("WOPIECE_ID_ICON_2"),
            placeholder="",
            mandatory=True,
            visible=True
        ),
        FormFieldConfig(
            field_id=GlueWorkpieceField.NAME.value,
            field_type="text",
            label=GlueWorkpieceField.NAME.getAsLabel(),
            icon_path=get_icon_path("WORKPIECE_NAME_ICON"),
            placeholder="",
            mandatory=False,
            visible=True
        ),
        FormFieldConfig(
            field_id=GlueWorkpieceField.DESCRIPTION.value,
            field_type="text",
            label=GlueWorkpieceField.DESCRIPTION.getAsLabel(),
            icon_path=get_icon_path("DESCRIPTION_WORKPIECE_BUTTON_SQUARE"),
            placeholder="",
            mandatory=False,
            visible=True
        ),
        FormFieldConfig(
            field_id=GlueWorkpieceField.HEIGHT.value,
            field_type="text",
            label=GlueWorkpieceField.HEIGHT.getAsLabel(),
            icon_path=get_contour_icon_path("RULER_ICON"),
            placeholder="",
            mandatory=True,
            visible=True
        ),
        FormFieldConfig(
            field_id=GlueWorkpieceField.GLUE_QTY.value,
            field_type="text",
            label=GlueWorkpieceField.GLUE_QTY.getAsLabel(),
            icon_path=get_icon_path("glue_qty"),
            placeholder="g /m²",
            mandatory=False,
            visible=True
        ),
        FormFieldConfig(
            field_id=GlueWorkpieceField.GRIPPER_ID.value,
            field_type="dropdown",
            label=GlueWorkpieceField.GRIPPER_ID.getAsLabel(),
            icon_path=get_icon_path("GRIPPER_ID_ICON"),
            options=[Gripper.SINGLE,Gripper.DOUBLE],
            mandatory=False,
            visible=True
        ),
        FormFieldConfig(
            field_id=GlueWorkpieceField.GLUE_TYPE.value,
            field_type="dropdown",
            label=GlueWorkpieceField.GLUE_TYPE.getAsLabel(),
            icon_path=get_icon_path("GLUE_TYPE_ICON"),
            options=glue_types,
            mandatory=True,
            visible=True
        )
    ]

    return GenericFormConfig(
        form_title="Create Workpiece",
        fields=fields,
        accept_button_icon="",
        cancel_button_icon="",
        config_file="settings/workpiece_form_config.json"
    )

