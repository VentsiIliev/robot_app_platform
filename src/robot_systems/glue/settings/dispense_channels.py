from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Sequence

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.shared_contracts.declarations import DispenseChannelDefinition


@dataclass(frozen=True)
class DispenseChannelConfig:
    channel_id: str
    glue_type: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DispenseChannelConfig":
        return cls(
            channel_id=str(data.get("channel_id", "")).strip(),
            glue_type=str(data.get("glue_type", "")).strip(),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel_id": str(self.channel_id).strip(),
            "glue_type": str(self.glue_type).strip(),
        }


@dataclass(frozen=True)
class DispenseChannelSettings:
    channels: List[DispenseChannelConfig] = field(default_factory=list)

    def get_channel(self, channel_id: str) -> DispenseChannelConfig | None:
        normalized = str(channel_id or "").strip()
        return next((c for c in self.channels if c.channel_id == normalized), None)


class DispenseChannelSettingsSerializer(ISettingsSerializer[DispenseChannelSettings]):
    def __init__(self, default_channels: Sequence[DispenseChannelDefinition] | None = None) -> None:
        self._default_channels = list(default_channels or [])

    @property
    def settings_type(self) -> str:
        return "dispense_channels"

    def get_default(self) -> DispenseChannelSettings:
        return DispenseChannelSettings(
            channels=[
                DispenseChannelConfig(
                    channel_id=definition.id,
                    glue_type=definition.default_glue_type,
                )
                for definition in self._default_channels
            ]
        )

    def to_dict(self, settings: DispenseChannelSettings) -> Dict[str, Any]:
        return {
            "channels": [channel.to_dict() for channel in settings.channels],
        }

    def from_dict(self, data: Dict[str, Any]) -> DispenseChannelSettings:
        raw_channels = data.get("channels")
        if raw_channels is None:
            return self.get_default()
        return DispenseChannelSettings(
            channels=[DispenseChannelConfig.from_dict(item) for item in raw_channels]
        )
