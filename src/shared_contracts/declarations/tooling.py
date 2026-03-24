from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    id: int
    name: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolDefinition":
        return cls(
            id=int(data.get("id", 0)),
            name=str(data.get("name", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": int(self.id),
            "name": str(self.name).strip(),
        }


@dataclass(frozen=True)
class ToolSlotDefinition:
    id: int
    tool_id: int | None = None
    pickup_movement_group_id: str = ""
    dropoff_movement_group_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolSlotDefinition":
        raw_tool_id = data.get("tool_id")
        return cls(
            id=int(data.get("id", data.get("slot_id", 0))),
            tool_id=int(raw_tool_id) if raw_tool_id is not None else None,
            pickup_movement_group_id=str(data.get("pickup_movement_group_id", "")).strip(),
            dropoff_movement_group_id=str(data.get("dropoff_movement_group_id", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": int(self.id),
            "tool_id": int(self.tool_id) if self.tool_id is not None else None,
            "pickup_movement_group_id": str(self.pickup_movement_group_id).strip(),
            "dropoff_movement_group_id": str(self.dropoff_movement_group_id).strip(),
        }
