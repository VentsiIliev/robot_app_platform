import json
import os
from ..models.settings_config import SettingsConfig


class SettingsService:
    _instance = None

    def __init__(self, settings_file_path=None):
        if settings_file_path is None:
            settings_file_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "global_segment_settings.json"
            )

        self.settings_file_path = settings_file_path
        self.default_settings = {}
        self._settings_groups = []
        self._combo_field_key = ""

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SettingsService()
        return cls._instance

    def configure(self, config: SettingsConfig):
        self.default_settings = dict(config.default_settings)
        self._settings_groups = list(config.groups)
        self._combo_field_key = config.combo_field_key

        self.initialize_default_settings()

    def load_from_file(self):
        try:
            if os.path.exists(self.settings_file_path):
                with open(self.settings_file_path, 'r') as f:
                    loaded_settings = json.load(f)
                return loaded_settings
            else:
                return {}
        except Exception as e:
            return {}

    def save_to_file(self, settings: dict):
        try:
            os.makedirs(os.path.dirname(self.settings_file_path), exist_ok=True)
            with open(self.settings_file_path, 'w') as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            pass

    def get_defaults(self):
        return self.default_settings.copy()

    def update_defaults(self, new_settings: dict):
        for key, value in new_settings.items():
            self.default_settings[key] = str(value)

        self.save_to_file(self.default_settings)

    def get_combo_field_key(self):
        return self._combo_field_key

    def get_settings_groups(self):
        return self._settings_groups

    def initialize_default_settings(self):
        file_settings = self.load_from_file()

        if file_settings:
            for key, value in file_settings.items():
                if key in self.default_settings:
                    self.default_settings[key] = str(value)

    def apply_to_all_segments(self, manager, settings: dict):
        for segment in manager.get_segments():
            segment.set_settings(settings)

