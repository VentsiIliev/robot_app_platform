from dataclasses import dataclass, field
from typing import Dict, Any

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass
class CameraSettings:
    data: Dict[str, Any] = field(default_factory=dict)


class CameraSettingsSerializer(ISettingsSerializer[CameraSettings]):

    @property
    def settings_type(self) -> str:
        return "camera_settings"

    def get_default(self) -> CameraSettings:
        from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import \
            CameraSettings as _VS_CameraSettings
        return CameraSettings(data=_VS_CameraSettings().to_dict())   # ← to_dict() not toDict()

    def to_dict(self, settings: CameraSettings) -> Dict[str, Any]:
        return settings.data

    def from_dict(self, data: Dict[str, Any]) -> CameraSettings:
        return CameraSettings(data=data)
