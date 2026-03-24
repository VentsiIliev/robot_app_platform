from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository


@dataclass
class DepthMapData:
    area_id: str = ""
    points: List[List[float]] = field(default_factory=list)  # [[x_mm, y_mm, height_mm], ...]
    marker_ids: List[int] = field(default_factory=list)
    point_labels: List[str] = field(default_factory=list)
    grid_rows: int = 0
    grid_cols: int = 0
    planned_points: List[List[float]] = field(default_factory=list)  # [[x_mm, y_mm], ...]
    planned_point_labels: List[str] = field(default_factory=list)
    unavailable_point_labels: List[str] = field(default_factory=list)

    def has_data(self) -> bool:
        return bool(self.points)


@dataclass
class DepthMapLibraryData:
    maps: Dict[str, DepthMapData] = field(default_factory=dict)

    def get(self, area_id: str) -> DepthMapData | None:
        return self.maps.get(area_id)

    def set(self, area_id: str, data: DepthMapData) -> None:
        self.maps[area_id] = data


class DepthMapLibraryDataSerializer(ISettingsSerializer[DepthMapLibraryData]):
    @property
    def settings_type(self) -> str:
        return "depth_map_library_data"

    def get_default(self) -> DepthMapLibraryData:
        return DepthMapLibraryData()

    def to_dict(self, data: DepthMapLibraryData) -> Dict[str, Any]:
        return {
            "maps": {
                str(area_id): _depth_map_to_dict(depth_map)
                for area_id, depth_map in data.maps.items()
            }
        }

    def from_dict(self, raw: Dict[str, Any]) -> DepthMapLibraryData:
        if "maps" in raw and isinstance(raw.get("maps"), dict):
            return DepthMapLibraryData(
                maps={
                    str(area_id): _depth_map_from_dict(map_raw)
                    for area_id, map_raw in raw["maps"].items()
                    if isinstance(map_raw, dict)
                }
            )
        legacy = _depth_map_from_dict(raw)
        if legacy.has_data():
            area_id = legacy.area_id or "default"
            return DepthMapLibraryData(maps={area_id: legacy})
        return DepthMapLibraryData()


class DepthMapDataSerializer(DepthMapLibraryDataSerializer):
    """Backwards-compatible alias for the common depth-map settings spec."""


class DepthMapRepository(BaseJsonSettingsRepository[DepthMapLibraryData]):
    def __init__(self, file_path: str):
        super().__init__(DepthMapDataSerializer(), file_path)


def _depth_map_to_dict(data: DepthMapData) -> Dict[str, Any]:
    return {
        "area_id": data.area_id,
        "points": data.points,
        "marker_ids": data.marker_ids,
        "point_labels": data.point_labels,
        "grid_rows": data.grid_rows,
        "grid_cols": data.grid_cols,
        "planned_points": data.planned_points,
        "planned_point_labels": data.planned_point_labels,
        "unavailable_point_labels": data.unavailable_point_labels,
    }


def _depth_map_from_dict(raw: Dict[str, Any]) -> DepthMapData:
    return DepthMapData(
            area_id=str(raw.get("area_id", "") or ""),
            points=raw.get("points", []),
            marker_ids=[int(v) for v in raw.get("marker_ids", [])],
            point_labels=[str(v) for v in raw.get("point_labels", [])],
            grid_rows=int(raw.get("grid_rows", 0) or 0),
            grid_cols=int(raw.get("grid_cols", 0) or 0),
            planned_points=raw.get("planned_points", []),
            planned_point_labels=[str(v) for v in raw.get("planned_point_labels", [])],
            unavailable_point_labels=[str(v) for v in raw.get("unavailable_point_labels", [])],
        )
