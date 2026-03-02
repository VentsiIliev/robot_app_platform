from contour_editor import ISettingsProvider
from typing import List, Dict


class GlueSettingsProvider(ISettingsProvider):
    """Settings provider for glue dispensing application"""

    def __init__(self, default_settings: Dict[str, str], material_types: List[str], material_type_key: str):
        self._default_settings = default_settings
        self._material_types = material_types
        self._material_type_key = material_type_key

    def get_all_setting_keys(self):
        return list(self._default_settings.keys())

    def get_default_values(self):
        return self._default_settings.copy()

    def get_material_type_key(self):
        return self._material_type_key

    def get_available_material_types(self):
        return self._material_types

    def get_default_material_type(self):
        return self._material_types[0] if self._material_types else ""

    def get_setting_label(self, key: str):
        return key.replace('_', ' ').title()

    def get_setting_value(self, key: str):
        return self._default_settings.get(key)

    def validate_setting(self, key: str, value: str) -> bool:
        if key not in self._default_settings:
            return False
        if not value or value.strip() == "":
            return False
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return key == self._material_type_key

    def validate_setting_value(self, key: str, value: str) -> bool:
        return self.validate_setting(key, value)

    def get_settings_tabs_config(self):
        return [("Settings", list(self._default_settings.keys()))]

