from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository


@dataclass
class DepthMapData:
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


class DepthMapDataSerializer(ISettingsSerializer[DepthMapData]):
    @property
    def settings_type(self) -> str:
        return "depth_map_data"

    def get_default(self) -> DepthMapData:
        return DepthMapData()

    def to_dict(self, data: DepthMapData) -> Dict[str, Any]:
        return {
            "points": data.points,
            "marker_ids": data.marker_ids,
            "point_labels": data.point_labels,
            "grid_rows": data.grid_rows,
            "grid_cols": data.grid_cols,
            "planned_points": data.planned_points,
            "planned_point_labels": data.planned_point_labels,
            "unavailable_point_labels": data.unavailable_point_labels,
        }

    def from_dict(self, raw: Dict[str, Any]) -> DepthMapData:
        return DepthMapData(
            points=raw.get("points", []),
            marker_ids=[int(v) for v in raw.get("marker_ids", [])],
            point_labels=[str(v) for v in raw.get("point_labels", [])],
            grid_rows=int(raw.get("grid_rows", 0) or 0),
            grid_cols=int(raw.get("grid_cols", 0) or 0),
            planned_points=raw.get("planned_points", []),
            planned_point_labels=[str(v) for v in raw.get("planned_point_labels", [])],
            unavailable_point_labels=[str(v) for v in raw.get("unavailable_point_labels", [])],
        )


class DepthMapRepository(BaseJsonSettingsRepository[DepthMapData]):
    def __init__(self, file_path: str):
        super().__init__(DepthMapDataSerializer(), file_path)
