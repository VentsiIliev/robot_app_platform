from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TargetFrameSettings:
    name: str
    source_navigation_group: str = ""
    target_navigation_group: str = ""
    use_height_correction: bool = False
    work_area_id: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetFrameSettings":
        return cls(
            name=str(data.get("name", "")).strip().lower(),
            source_navigation_group=str(data.get("source_navigation_group", "")).strip(),
            target_navigation_group=str(data.get("target_navigation_group", "")).strip(),
            use_height_correction=bool(data.get("use_height_correction", False)),
            work_area_id=str(data.get("work_area_id", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": str(self.name).strip().lower(),
            "source_navigation_group": str(self.source_navigation_group).strip(),
            "target_navigation_group": str(self.target_navigation_group).strip(),
            "use_height_correction": bool(self.use_height_correction),
            "work_area_id": str(self.work_area_id).strip(),
        }
