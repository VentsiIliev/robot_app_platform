from dataclasses import dataclass
from contour_editor import SettingsConfig, SettingsGroup, ISettingsProvider
from src.applications.workpiece_editor.editor_core.config.segment_settings_schema import SegmentSettingsSchema
from src.applications.workpiece_editor.editor_core.config.segment_settings_provider_adapter import SegmentSettingsProviderAdapter


@dataclass
class SegmentEditorConfig:
    schema: SegmentSettingsSchema

    @property
    def settings_provider(self) -> ISettingsProvider:
        return SegmentSettingsProviderAdapter(self.schema)

    @property
    def settings_config(self) -> SettingsConfig:
        groups = [SettingsGroup(name, keys) for name, keys in self.schema.get_groups().items()]
        return SettingsConfig(
            default_settings = self.schema.get_defaults(),
            groups           = groups,
            combo_field_key  = self.schema.combo_key,
        )
