from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    id: int
    name: str
    reference_tool_id: int | None = None
    relative_transform: tuple[float, float, float, float, float, float] = (0, 0, 0, 0, 0, 0)
    collision_profile: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolDefinition":
        raw_transform = data.get("relative_transform", [0, 0, 0, 0, 0, 0])
        if len(raw_transform) != 6:
            raise ValueError("relative_transform must contain six values")
        raw_reference = data.get("reference_tool_id")
        return cls(
            id=int(data.get("id", 0)),
            name=str(data.get("name", "")).strip(),
            reference_tool_id=int(raw_reference) if raw_reference is not None else None,
            relative_transform=tuple(float(value) for value in raw_transform),
            collision_profile=str(data.get("collision_profile", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        result = {
            "id": int(self.id),
            "name": str(self.name).strip(),
        }
        if self.reference_tool_id is not None:
            result["reference_tool_id"] = int(self.reference_tool_id)
        if any(float(value) != 0.0 for value in self.relative_transform):
            result["relative_transform"] = [float(value) for value in self.relative_transform]
        if self.collision_profile:
            result["collision_profile"] = str(self.collision_profile).strip()
        return result


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
