import os
from src.applications.workpiece_editor.editor_core.config.workpiece_form_schema import WorkpieceFormSchema
from src.applications.workpiece_editor.editor_core.ui.CreateWorkpieceForm import GenericFormConfig, FormFieldConfig


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




def create_workpiece_form_config(schema: WorkpieceFormSchema) -> GenericFormConfig:
    fields = [
        FormFieldConfig(
            field_id      = spec.key,
            field_type    = spec.field_type,
            label         = spec.label,
            icon          = spec.icon,
            placeholder   = spec.placeholder,
            default_value = spec.default_value,
            mandatory     = spec.mandatory,
            visible       = spec.visible,
            options       = spec.options or [],
        )
        for spec in schema.fields
    ]
    return GenericFormConfig(
        form_title          = "Create Workpiece",
        fields              = fields,
        accept_button_icon  = "",
        cancel_button_icon  = "",
        config_file         = "settings/workpiece_form_config.json",
    )
