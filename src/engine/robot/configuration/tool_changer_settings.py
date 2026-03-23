from dataclasses import dataclass, field
from typing import List

from src.engine.repositories.interfaces import ISettingsSerializer
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig

_DEFAULT_TOOLS = [
    {"id": 0, "name": "TOOL 1"},
    {"id": 1, "name": "TOOL 2"},
    {"id": 4, "name": "TOOL 3"},
]

_DEFAULT_SLOTS = [
    {"slot_id": 10, "tool_id": 0},
    {"slot_id": 11, "tool_id": 1},
    {"slot_id": 12, "tool_id": 4},
]


@dataclass
class ToolChangerSettings:
    tools: List[ToolDefinition] = field(default_factory=list)
    slots: List[SlotConfig] = field(default_factory=list)

    def get_tool_names(self) -> List[str]:
        return [t.name for t in self.tools]

    def get_tool_options(self) -> List[ToolDefinition]:
        return list(self.tools)


class ToolChangerSettingsSerializer(ISettingsSerializer):
    @property
    def settings_type(self) -> str:
        return "tool_changer"

    def get_default(self) -> ToolChangerSettings:
        return self._from_raw({"tools": _DEFAULT_TOOLS, "slots": _DEFAULT_SLOTS})

    def to_dict(self, settings: ToolChangerSettings) -> dict:
        return {
            "tools": [{"id": t.id, "name": t.name} for t in settings.tools],
            "slots": [{"slot_id": s.id, "tool_id": s.tool_id} for s in settings.slots],
        }

    def from_dict(self, data: dict) -> ToolChangerSettings:
        return self._from_raw(data)

    @staticmethod
    def _from_raw(data: dict) -> ToolChangerSettings:
        tools = [
            ToolDefinition(id=int(t["id"]), name=str(t["name"]))
            for t in data.get("tools", _DEFAULT_TOOLS)
        ]
        slots = [
            SlotConfig(
                id=int(s["slot_id"]),
                tool_id=int(s["tool_id"]) if s.get("tool_id") is not None else None,
            )
            for s in data.get("slots", _DEFAULT_SLOTS)
        ]
        return ToolChangerSettings(tools=tools, slots=slots)
