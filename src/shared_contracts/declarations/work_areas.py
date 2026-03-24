from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkAreaDefinition:
    id: str
    label: str
    color: str
    threshold_profile: str = "default"
    supports_detection_roi: bool = True
    supports_brightness_roi: bool = False
    supports_height_mapping: bool = False

    def detection_area_key(self) -> str:
        return self.id

    def brightness_area_key(self) -> str:
        return f"{self.id}__brightness"

    def height_mapping_area_key(self) -> str:
        return f"{self.id}__height_mapping"


@dataclass(frozen=True)
class WorkAreaObserverBinding:
    area_id: str
    movement_group_id: str
