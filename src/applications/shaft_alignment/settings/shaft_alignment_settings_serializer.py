from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings
from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


class ShaftAlignmentSettingsSerializer(ISettingsSerializer[ShaftAlignmentSettings]):
    @property
    def settings_type(self) -> str:
        return "shaft_alignment"

    def get_default(self) -> ShaftAlignmentSettings:
        return ShaftAlignmentSettings()

    def to_dict(self, settings: ShaftAlignmentSettings) -> dict:
        settings.validate()
        return settings.to_dict()

    def from_dict(self, data: dict) -> ShaftAlignmentSettings:
        return ShaftAlignmentSettings.from_dict(data)
