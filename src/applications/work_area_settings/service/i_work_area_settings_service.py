from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class IWorkAreaSettingsService(ABC):
    @abstractmethod
    def get_active_work_area_id(self) -> str:
        ...

    @abstractmethod
    def set_active_work_area_id(self, area_id: str) -> None:
        ...

    @abstractmethod
    def save_work_area(
        self,
        area_key: str,
        normalized_points: List[Tuple[float, float]],
    ) -> tuple[bool, str]:
        ...

    @abstractmethod
    def get_work_area(
        self,
        area_key: str,
    ) -> tuple[bool, str, Optional[List[Tuple[float, float]]]]:
        ...
