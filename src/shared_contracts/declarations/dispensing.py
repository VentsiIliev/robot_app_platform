from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class DispenseChannelDefinition:
    id: str
    label: str
    weight_cell_id: int
    pump_motor_address: int
    default_glue_type: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DispenseChannelDefinition":
        return cls(
            id=str(data.get("id", "")).strip(),
            label=str(data.get("label", "")).strip(),
            weight_cell_id=int(data.get("weight_cell_id", 0)),
            pump_motor_address=int(data.get("pump_motor_address", 0)),
            default_glue_type=str(data.get("default_glue_type", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id).strip(),
            "label": str(self.label).strip(),
            "weight_cell_id": int(self.weight_cell_id),
            "pump_motor_address": int(self.pump_motor_address),
            "default_glue_type": str(self.default_glue_type).strip(),
        }
