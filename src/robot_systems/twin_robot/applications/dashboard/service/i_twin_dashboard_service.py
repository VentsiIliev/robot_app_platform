from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class ITwinDashboardService(ABC):
    @abstractmethod
    def list_choreographies(self) -> List[Dict[str, Any]]:
        ...

    @abstractmethod
    def select(self, choreography_id: str) -> Dict[str, Any]:
        ...

    @abstractmethod
    def plan_selected(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def prepared_status(self) -> Dict[str, Any]:
        ...

    @abstractmethod
    def start(self, loop_count: int | None = None) -> Dict[str, Any]:
        ...

    @abstractmethod
    def stop(self) -> Dict[str, Any]:
        ...
