from dataclasses import dataclass, field
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer
from src.engine.repositories.json.base_json_settings_repository import BaseJsonSettingsRepository


@dataclass
class DepthMapData:
    points: List[List[float]] = field(default_factory=list)  # [[x_mm, y_mm, height_mm], ...]

    def has_data(self) -> bool:
        return bool(self.points)


class DepthMapDataSerializer(ISettingsSerializer[DepthMapData]):
    @property
    def settings_type(self) -> str:
        return "depth_map_data"

    def get_default(self) -> DepthMapData:
        return DepthMapData()

    def to_dict(self, data: DepthMapData) -> Dict[str, Any]:
        return {"points": data.points}

    def from_dict(self, raw: Dict[str, Any]) -> DepthMapData:
        return DepthMapData(points=raw.get("points", []))


class DepthMapRepository(BaseJsonSettingsRepository[DepthMapData]):
    def __init__(self, file_path: str):
        super().__init__(DepthMapDataSerializer(), file_path)

