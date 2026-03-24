from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RemoteTcpSettings:
    name: str
    display_name: str = ""
    x_mm: float = 0.0
    y_mm: float = 0.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteTcpSettings":
        return cls(
            name=str(data.get("name", "")).strip().lower(),
            display_name=str(data.get("display_name", "")).strip(),
            x_mm=float(data.get("x_mm", 0.0)),
            y_mm=float(data.get("y_mm", 0.0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": str(self.name).strip().lower(),
            "display_name": str(self.display_name).strip(),
            "x_mm": float(self.x_mm),
            "y_mm": float(self.y_mm),
        }
