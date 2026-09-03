from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.robot_systems.twin_robot.applications.dashboard.service.i_twin_dashboard_service import (
    ITwinDashboardService,
)
from src.robot_systems.twin_robot.domain import ChoreographyDefinition
from src.robot_systems.twin_robot.storage import ChoreographyRepository


class TwinDashboardService(ITwinDashboardService):
    """Operator-facing choreography selection and execution coordinator."""

    def __init__(self, repository: ChoreographyRepository, runtime: Any | None = None):
        self._repository = repository
        self._runtime = runtime
        self._selected_id: Optional[str] = None
        self._prepared: Any | None = None

    def set_runtime(self, runtime: Any | None) -> None:
        self._runtime = runtime
        self._prepared = None

    def list_choreographies(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._repository.list()]

    def select(self, choreography_id: str) -> Dict[str, Any]:
        choreography = self._repository.get(choreography_id)
        self._selected_id = choreography.choreography_id
        self._prepared = None
        return choreography.to_dict()

    def _selected_definition(self) -> ChoreographyDefinition | None:
        if not self._selected_id:
            return None
        try:
            return self._repository.get(self._selected_id)
        except FileNotFoundError:
            self._selected_id = None
            self._prepared = None
            return None

    def plan_selected(self) -> Dict[str, Any]:
        choreography = self._selected_definition()
        if choreography is None:
            return {"success": False, "error": "No choreography selected"}

        errors = choreography.validate()
        if errors:
            return {"success": False, "error": "; ".join(errors)}

        if self._runtime is None:
            self._prepared = None
            return {
                "success": False,
                "error": "Twin runtime adapter is not connected yet",
                "robot1_ready": False,
                "robot2_ready": False,
            }

        prepare = getattr(self._runtime, "prepare_choreography", None)
        if not callable(prepare):
            return {
                "success": False,
                "error": "Twin runtime does not support prepare_choreography",
                "robot1_ready": False,
                "robot2_ready": False,
            }

        self._prepared = prepare(choreography)
        status = self.prepared_status()
        return {"success": bool(status.get("ready")), **status}

    def prepared_status(self) -> Dict[str, Any]:
        if self._prepared is None:
            return {
                "ready": False,
                "robot1_ready": False,
                "robot2_ready": False,
            }

        if isinstance(self._prepared, dict):
            r1 = bool(self._prepared.get("robot1_ready", False))
            r2 = bool(self._prepared.get("robot2_ready", False))
            return {**self._prepared, "ready": bool(r1 and r2)}

        r1 = bool(getattr(self._prepared, "robot1_ready", False))
        r2 = bool(getattr(self._prepared, "robot2_ready", False))
        return {
            "ready": r1 and r2,
            "robot1_ready": r1,
            "robot2_ready": r2,
        }

    def start(self, loop_count: int | None = None) -> Dict[str, Any]:
        status = self.prepared_status()
        if not status.get("ready"):
            return {
                "success": False,
                "error": "Both robot trajectories must be prepared before start",
            }
        if self._runtime is None:
            return {"success": False, "error": "Twin runtime adapter is not connected"}

        execute = getattr(self._runtime, "execute_prepared", None)
        if not callable(execute):
            return {
                "success": False,
                "error": "Twin runtime does not support execute_prepared",
            }

        choreography = self._selected_definition()
        count = int(loop_count or (choreography.loop_count if choreography else 1))
        result = execute(self._prepared, loop_count=max(1, count))
        return result if isinstance(result, dict) else {"success": bool(result)}

    def stop(self) -> Dict[str, Any]:
        if self._runtime is None:
            return {"success": True, "stopped": False}
        stop = getattr(self._runtime, "stop", None)
        if not callable(stop):
            return {"success": False, "error": "Twin runtime does not support stop"}
        result = stop()
        return result if isinstance(result, dict) else {"success": bool(result)}
