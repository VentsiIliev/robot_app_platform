from contour_editor import ISettingsProvider
from src.applications.workpiece_editor.editor_core.config.segment_settings_schema import SegmentSettingsSchema


class SegmentSettingsProviderAdapter(ISettingsProvider):
    """
    Adapts SegmentSettingsSchema to the contour_editor.ISettingsProvider interface.
    Method names (get_material_type_key etc.) are fixed by the external contract
    and do not imply any domain knowledge — they map to combo_key / combo_options.
    """

    def __init__(self, schema: SegmentSettingsSchema):
        self._schema = schema

    def get_all_setting_keys(self):
        return list(self._schema.get_defaults().keys())

    def get_default_values(self):
        return self._schema.get_defaults()

    def get_material_type_key(self):           # ISettingsProvider contract
        return self._schema.combo_key

    def get_available_material_types(self):    # ISettingsProvider contract
        # Some systems (e.g. paint/welding test editors) have per-segment
        # settings but no material-type combo field. The contour editor's
        # settings dialog still expects a non-empty list here to consider the
        # settings provider "connected", so return a benign placeholder.
        return self._schema.combo_options or ["Settings"]

    def get_default_material_type(self):       # ISettingsProvider contract
        return self._schema.combo_options[0] if self._schema.combo_options else "Settings"

    def get_setting_label(self, key: str):
        return self._schema.get_label(key)

    def get_setting_value(self, key: str):
        return self._schema.get_defaults().get(key)

    def validate_setting(self, key: str, value: str) -> bool:
        return self._schema.validate(key, value)

    def validate_setting_value(self, key: str, value: str) -> bool:
        return self._schema.validate(key, value)

    def get_settings_tabs_config(self):
        return [("Settings", list(self._schema.get_defaults().keys()))]
