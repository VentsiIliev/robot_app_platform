from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces import ISettingsSerializer


NormalizedPolygon = List[List[float]]


@dataclass
class WorkAreaConfig:
    detection_roi: NormalizedPolygon = field(default_factory=list)
    brightness_roi: NormalizedPolygon = field(default_factory=list)
    height_mapping_roi: NormalizedPolygon = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "WorkAreaConfig":
        return cls(
            detection_roi=_load_polygon(raw.get("detection_roi")),
            brightness_roi=_load_polygon(raw.get("brightness_roi")),
            height_mapping_roi=_load_polygon(raw.get("height_mapping_roi")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "detection_roi": [list(point) for point in self.detection_roi],
            "brightness_roi": [list(point) for point in self.brightness_roi],
            "height_mapping_roi": [list(point) for point in self.height_mapping_roi],
        }


@dataclass
class WorkAreaSettings:
    areas: Dict[str, WorkAreaConfig] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "WorkAreaSettings":
        areas_raw = raw.get("areas", {})
        if not isinstance(areas_raw, dict):
            areas_raw = {}
        return cls(
            areas={
                str(area_id): WorkAreaConfig.from_dict(area_data)
                for area_id, area_data in areas_raw.items()
                if isinstance(area_data, dict)
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "areas": {
                str(area_id): config.to_dict()
                for area_id, config in self.areas.items()
            }
        }


class WorkAreaSettingsSerializer(ISettingsSerializer[WorkAreaSettings]):
    @property
    def settings_type(self) -> str:
        return "work_area_settings"

    def get_default(self) -> WorkAreaSettings:
        return WorkAreaSettings()

    def to_dict(self, data: WorkAreaSettings) -> Dict[str, Any]:
        return data.to_dict()

    def from_dict(self, raw: Dict[str, Any]) -> WorkAreaSettings:
        return WorkAreaSettings.from_dict(raw)


def _load_polygon(raw: Any) -> NormalizedPolygon:
    if not isinstance(raw, list):
        return []
    points: NormalizedPolygon = []
    for point in raw:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            continue
        points.append([float(point[0]), float(point[1])])
    return points
