from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Optional

from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.twin_robot.applications.choreography_setup.service.i_choreography_setup_service import (
    IChoreographySetupService,
)


_DEFAULT_MOTION = {"velocity": 30.0, "acceleration": 30.0}


class ChoreographySetupModel(IApplicationModel):
    def __init__(self, service: IChoreographySetupService):
        self._service = service
        self._current: Optional[Dict[str, Any]] = None

    def load(self) -> List[Dict[str, Any]]:
        return self._service.list_choreographies()

    def load_choreography(self, choreography_id: str) -> Dict[str, Any]:
        self._current = self._service.load_choreography(choreography_id)
        return self.current()

    def new_choreography(self, choreography_id: str, name: str) -> Dict[str, Any]:
        self._current = self._service.new_choreography(choreography_id, name)
        return self.current()

    def current(self) -> Dict[str, Any]:
        return deepcopy(self._current or {})

    def apply_editor(self, *, name: str, loop_count: int, steps: List[Dict[str, Any]]) -> None:
        if self._current is None:
            raise RuntimeError("Create or load a choreography first")
        self._current["name"] = str(name).strip()
        self._current["loop_count"] = max(1, int(loop_count))

        current_steps = list(self._current.get("steps", []))
        for row, edit in enumerate(steps):
            if row >= len(current_steps):
                break
            step = current_steps[row]
            step["name"] = str(edit.get("name", step.get("name", f"Step {row + 1}"))).strip()
            step["robot1_motion"] = self._motion_from_edit(
                edit.get("robot1_velocity"), edit.get("robot1_acceleration")
            )
            step["robot2_motion"] = self._motion_from_edit(
                edit.get("robot2_velocity"), edit.get("robot2_acceleration")
            )
        self._current["steps"] = current_steps

    def add_step(self) -> Dict[str, Any]:
        if self._current is None:
            raise RuntimeError("Create or load a choreography first")
        steps = self._current.setdefault("steps", [])
        steps.append(
            {
                "name": f"Step {len(steps) + 1}",
                "robot1": {"pose": [], "joints": []},
                "robot2": {"pose": [], "joints": []},
                "robot1_motion": dict(_DEFAULT_MOTION),
                "robot2_motion": dict(_DEFAULT_MOTION),
            }
        )
        return self.current()

    def delete_step(self, row: int) -> Dict[str, Any]:
        if self._current is None:
            raise RuntimeError("Create or load a choreography first")
        steps = self._current.setdefault("steps", [])
        if not 0 <= int(row) < len(steps):
            raise IndexError("Invalid choreography step")
        if int(row) == 0:
            raise ValueError("The Start step cannot be deleted")
        del steps[int(row)]
        return self.current()

    def capture_robot(self, row: int, robot_name: str) -> Dict[str, Any]:
        step = self._step(row)
        captured = self._service.capture_robot(robot_name)
        step[robot_name] = deepcopy(captured)
        return self.current()

    def capture_both(self, row: int) -> Dict[str, Any]:
        step = self._step(row)
        step["robot1"] = deepcopy(self._service.capture_robot("robot1"))
        step["robot2"] = deepcopy(self._service.capture_robot("robot2"))
        return self.current()

    def save(self) -> Dict[str, Any]:
        if self._current is None:
            raise RuntimeError("Nothing to save")
        result = self._service.save_choreography(self._current)
        saved = result.get("choreography") if isinstance(result, dict) else None
        if isinstance(saved, dict):
            self._current = deepcopy(saved)
        return result

    def robot_states(self) -> Dict[str, Dict[str, Any]]:
        return {
            "robot1": self._service.robot_state("robot1"),
            "robot2": self._service.robot_state("robot2"),
        }

    def jog(self, robot_name: str, command: str, axis: str, direction: str, step: float) -> int:
        return self._service.jog(robot_name, command, axis, direction, step)

    def stop_servo_jog(self, robot_name: str) -> int:
        return self._service.stop_servo_jog(robot_name)

    def joint_jog(
        self,
        robot_name: str,
        command: str,
        joint: str,
        direction: str,
        step: float,
    ) -> int:
        return self._service.joint_jog(robot_name, command, joint, direction, step)

    def _step(self, row: int) -> Dict[str, Any]:
        if self._current is None:
            raise RuntimeError("Create or load a choreography first")
        steps = self._current.setdefault("steps", [])
        if not 0 <= int(row) < len(steps):
            raise IndexError("Invalid choreography step")
        return steps[int(row)]

    @staticmethod
    def _motion_from_edit(velocity, acceleration) -> Dict[str, float]:
        return {
            "velocity": float(velocity if velocity is not None else 30.0),
            "acceleration": float(acceleration if acceleration is not None else 30.0),
        }
