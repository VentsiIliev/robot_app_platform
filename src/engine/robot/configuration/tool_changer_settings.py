from dataclasses import dataclass, field
from typing import List, Sequence

from src.engine.repositories.interfaces import ISettingsSerializer
from src.engine.robot.interfaces.tool_definition import ToolDefinition
from src.engine.robot.tool_changer import SlotConfig
from src.shared_contracts.declarations.tooling import ToolDefinition as ToolDefinitionDeclaration
from src.shared_contracts.declarations.tooling import ToolSlotDefinition


@dataclass
class ToolChangerSettings:
    tools: List[ToolDefinition] = field(default_factory=list)
    slots: List[SlotConfig] = field(default_factory=list)

    def get_tool_names(self) -> List[str]:
        return [t.name for t in self.tools]

    def get_tool_options(self) -> List[ToolDefinition]:
        return list(self.tools)


class ToolChangerSettingsSerializer(ISettingsSerializer):
    def __init__(
        self,
        default_tools: Sequence[ToolDefinitionDeclaration] | None = None,
        default_slots: Sequence[ToolSlotDefinition] | None = None,
    ) -> None:
        self._default_tools = list(default_tools or [])
        self._default_slots = list(default_slots or [])

    @property
    def settings_type(self) -> str:
        return "tool_changer"

    def get_default(self) -> ToolChangerSettings:
        return ToolChangerSettings(
            tools=[
                ToolDefinition(id=int(tool.id), name=str(tool.name))
                for tool in self._default_tools
            ],
            slots=[
                SlotConfig(id=int(slot.id), tool_id=slot.tool_id)
                for slot in self._default_slots
            ],
        )

    def to_dict(self, settings: ToolChangerSettings) -> dict:
        return {
            "tools": [{"id": t.id, "name": t.name} for t in settings.tools],
            "slots": [{"slot_id": s.id, "tool_id": s.tool_id} for s in settings.slots],
        }

    def from_dict(self, data: dict) -> ToolChangerSettings:
        return self._from_raw(data)

    def _from_raw(self, data: dict) -> ToolChangerSettings:
        raw_tools = data.get("tools")
        raw_slots = data.get("slots")
        tools = [
            ToolDefinition(id=int(t["id"]), name=str(t["name"]))
            for t in (raw_tools if raw_tools is not None else [tool.to_dict() for tool in self._default_tools])
        ]
        slots = [
            SlotConfig(
                id=int(s["slot_id"]),
                tool_id=int(s["tool_id"]) if s.get("tool_id") is not None else None,
            )
            for s in (
                raw_slots
                if raw_slots is not None
                else [{"slot_id": slot.id, "tool_id": slot.tool_id} for slot in self._default_slots]
            )
        ]
        return ToolChangerSettings(tools=tools, slots=slots)
