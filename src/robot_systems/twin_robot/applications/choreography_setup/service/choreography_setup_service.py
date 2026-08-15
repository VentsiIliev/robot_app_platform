from __future__ import annotations

from typing import Any, Dict, List

from src.robot_systems.twin_robot.applications.choreography_setup.service.i_choreography_setup_service import (
    IChoreographySetupService,
)
from src.robot_systems.twin_robot.domain import ChoreographyDefinition, ChoreographyStep
from src.robot_systems.twin_robot.storage import ChoreographyRepository


class ChoreographySetupService(IChoreographySetupService):
    def __init__(self, repository: ChoreographyRepository, runtime: Any | None = None):
        self._repository = repository
        self._runtime = runtime

    def set_runtime(self, runtime: Any | None) -> None:
        self._runtime = runtime

    def list_choreographies(self) -> List[Dict[str, Any]]:
        return [item.to_dict() for item in self._repository.list()]

    def load_choreography(self, choreography_id: str) -> Dict[str, Any]:
        return self._repository.get(choreography_id).to_dict()

    def new_choreography(self, choreography_id: str, name: str) -> Dict[str, Any]:
        return ChoreographyDefinition(
            choreography_id=str(choreography_id).strip(),
            name=str(name).strip(),
            steps=[ChoreographyStep(name="Start")],
        ).to_dict()

    def save_choreography(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        choreography = ChoreographyDefinition.from_dict(payload)
        errors = choreography.validate()
        self._repository.save(choreography)
        return {
            "success": True,
            "warnings": errors,
            "choreography": choreography.to_dict(),
        }

    def capture_robot(self, robot_name: str) -> Dict[str, Any]:
        robot = self._robot(robot_name)
        position = robot.get_current_position()
        if position is None or len(position) < 6:
            raise RuntimeError(f"{robot_name} Cartesian position unavailable")

        joints = self._joint_positions(robot)
        if len(joints) != 6:
            raise RuntimeError(f"{robot_name} six-joint state unavailable")

        return {
            "pose": [float(v) for v in position[:6]],
            "joints": [float(v) for v in joints],
        }

    def robot_state(self, robot_name: str) -> Dict[str, Any]:
        return self.capture_robot(robot_name)

    def jog(
        self,
        robot_name: str,
        command: str,
        axis: str,
        direction: str,
        step: float,
    ) -> int:
        robot = self._robot(robot_name)
        command = str(command or "JOG_ROBOT").strip().upper()
        if command == "JOG_ROBOT":
            return int(
                robot.jog(
                    axis=str(axis).lower(),
                    direction=direction,
                    step=float(step),
                    vel=20,
                    acc=20,
                )
            )
        if command == "SERVO_JOG":
            method = getattr(robot, "servo_jog_start", None)
            if not callable(method):
                raise RuntimeError("Twin runtime adapter does not expose servo jogging yet")
            upper_axis = str(axis).upper()
            return int(
                method(
                    axis=str(axis).lower(),
                    direction=direction,
                    vel=20,
                    acc=20,
                    linear_mm_s=float(step) if upper_axis in {"X", "Y", "Z"} else None,
                    angular_deg_s=float(step) if upper_axis in {"RX", "RY", "RZ"} else None,
                )
            )
        raise RuntimeError(f"Unsupported jog command: {command}")

    def stop_servo_jog(self, robot_name: str) -> int:
        robot = self._robot(robot_name)
        method = getattr(robot, "servo_jog_stop", None)
        if not callable(method):
            return 0
        return int(method())

    def joint_jog(
        self,
        robot_name: str,
        command: str,
        joint: str,
        direction: str,
        step: float,
    ) -> int:
        robot = self._robot(robot_name)
        method = getattr(robot, "joint_jog", None) or getattr(robot, "jog_joint", None)
        if not callable(method):
            raise RuntimeError("Twin runtime adapter does not expose joint jogging yet")
        return int(method(joint=joint, direction=direction, step=float(step)))

    @staticmethod
    def _joint_positions(robot) -> List[float]:
        get_joints = getattr(robot, "get_current_joints", None)
        if callable(get_joints):
            joints = list(get_joints() or [])
            if joints:
                return [float(v) for v in joints]

        node = getattr(robot, "node", None)
        state = getattr(node, "current_joint_state", None)
        return [float(v) for v in (getattr(state, "position", []) or [])]

    def _robot(self, robot_name: str):
        if self._runtime is None:
            raise RuntimeError("Twin runtime adapter is not connected yet")
        getter = getattr(self._runtime, "robot", None)
        if callable(getter):
            robot = getter(robot_name)
        else:
            robot = getattr(self._runtime, robot_name, None)
        if robot is None:
            raise RuntimeError(f"Twin runtime has no {robot_name}")
        return robot
