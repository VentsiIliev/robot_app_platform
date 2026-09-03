from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.twin_robot.applications.dashboard.service.i_twin_dashboard_service import (
    ITwinDashboardService,
)


class TwinDashboardModel(IApplicationModel):
    def __init__(self, service: ITwinDashboardService):
        self._service = service
        self._choreographies: List[Dict[str, Any]] = []
        self._selected: Optional[Dict[str, Any]] = None

    def load(self) -> List[Dict[str, Any]]:
        self._choreographies = self._service.list_choreographies()
        return list(self._choreographies)

    def select(self, choreography_id: str) -> Dict[str, Any]:
        self._selected = self._service.select(choreography_id)
        return dict(self._selected)

    def plan(self) -> Dict[str, Any]:
        return self._service.plan_selected()

    def prepared_status(self) -> Dict[str, Any]:
        return self._service.prepared_status()

    def start(self, loop_count: int) -> Dict[str, Any]:
        return self._service.start(loop_count=loop_count)

    def stop_motion(self) -> Dict[str, Any]:
        return self._service.stop()

    @property
    def selected(self) -> Optional[Dict[str, Any]]:
        return dict(self._selected) if self._selected is not None else None
