from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.robot.configuration.robot_settings import MovementGroup


@dataclass
class MovementGroupSettings:
    movement_groups: Dict[str, MovementGroup] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MovementGroupSettings":
        groups_raw = data.get("MOVEMENT_GROUPS", data.get("movement_groups", {}))
        movement_groups = {
            name: MovementGroup.from_dict(group_data)
            for name, group_data in groups_raw.items()
        }
        return cls(movement_groups=movement_groups)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "MOVEMENT_GROUPS": {
                name: group.to_dict()
                for name, group in self.movement_groups.items()
            }
        }


class MovementGroupSettingsSerializer(ISettingsSerializer[MovementGroupSettings]):
    @property
    def settings_type(self) -> str:
        return "movement_group_settings"

    def get_default(self) -> MovementGroupSettings:
        return MovementGroupSettings()

    def to_dict(self, settings: MovementGroupSettings) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> MovementGroupSettings:
        return MovementGroupSettings.from_dict(data)
