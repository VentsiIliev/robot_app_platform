from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RemoteTcpDefinition:
    name: str
    display_name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RemoteTcpDefinition":
        return cls(
            name=str(data.get("name", "")).strip().lower(),
            display_name=str(data.get("display_name", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": str(self.name).strip().lower(),
            "display_name": str(self.display_name).strip() or str(self.name).strip().lower(),
        }


@dataclass(frozen=True)
class TargetFrameDefinition:
    name: str
    work_area_id: str = ""
    source_navigation_group: str = ""
    target_navigation_group: str = ""
    use_height_correction: bool = False
    display_name: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TargetFrameDefinition":
        return cls(
            name=str(data.get("name", "")).strip().lower(),
            work_area_id=str(data.get("work_area_id", "")).strip(),
            source_navigation_group=str(data.get("source_navigation_group", "")).strip(),
            target_navigation_group=str(data.get("target_navigation_group", "")).strip(),
            use_height_correction=bool(data.get("use_height_correction", False)),
            display_name=str(data.get("display_name", "")).strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": str(self.name).strip().lower(),
            "work_area_id": str(self.work_area_id).strip(),
            "source_navigation_group": str(self.source_navigation_group).strip(),
            "target_navigation_group": str(self.target_navigation_group).strip(),
            "use_height_correction": bool(self.use_height_correction),
            "display_name": str(self.display_name).strip() or str(self.name).strip().lower(),
        }
