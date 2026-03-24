from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from src.engine.work_areas.work_area_settings import NormalizedPolygon, WorkAreaConfig
from src.shared_contracts.declarations import WorkAreaDefinition


class IWorkAreaService(ABC):
    @abstractmethod
    def get_active_area_id(self) -> Optional[str]:
        ...

    @abstractmethod
    def set_active_area_id(self, area_id: str | None) -> None:
        ...

    @abstractmethod
    def get_area_config(self, area_id: str) -> WorkAreaConfig | None:
        ...

    @abstractmethod
    def get_area_definition(self, area_id: str) -> WorkAreaDefinition | None:
        ...

    @abstractmethod
    def save_work_area(self, area_key: str, normalized_points: NormalizedPolygon) -> tuple[bool, str]:
        ...

    @abstractmethod
    def get_work_area(self, area_key: str) -> NormalizedPolygon | None:
        ...

    @abstractmethod
    def get_detection_roi_pixels(self, area_id: str, width: int, height: int):
        ...

    @abstractmethod
    def get_brightness_roi_pixels(self, area_id: str, width: int, height: int):
        ...
