from __future__ import annotations

from typing import Any, List

from src.robot_systems.twin_robot.domain import (
    ChoreographyDefinition,
    ChoreographyStep,
    RobotChoreographyPose,
)
from src.robot_systems.twin_robot.storage import ChoreographyRepository


class ChoreographySetupService:
    def __init__(self, repository: ChoreographyRepository, runtime: Any | None = None):
        self._repository = repository
        self._runtime = runtime

    def list(self) -> List[ChoreographyDefinition]:
        return self._repository.list()

    def load(self, choreography_id: str) -> ChoreographyDefinition:
        return self._repository.get(choreography_id)

    def save(self, choreography: ChoreographyDefinition) -> None:
        self._repository.save(choreography)

    def delete(self, choreography_id: str) -> None:
        self._repository.delete(choreography_id)

    def new(self, choreography_id: str, name: str) -> ChoreographyDefinition:
        return ChoreographyDefinition(
            choreography_id=choreography_id.strip(),
            name=name.strip(),
            steps=[ChoreographyStep(name="Start")],
        )

    def capture_robot(self, robot_name: str) -> RobotChoreographyPose:
        robot = self._robot(robot_name)
        position = robot.get_current_position()
        if position is None or len(position) < 6:
            raise RuntimeError(f"{robot_name} Cartesian position unavailable")

        joints = []
        get_joints = getattr(robot, "get_current_joints", None)
        if callable(get_joints):
            joints = list(get_joints() or [])
        else:
            node = getattr(robot, "node", None)
            state = getattr(node, "current_joint_state", None)
            joints = list(getattr(state, "position", []) or [])

        if len(joints) != 6:
            raise RuntimeError(f"{robot_name} six-joint state unavailable")
        return RobotChoreographyPose(
            pose=[float(v) for v in position[:6]],
            joints=[float(v) for v in joints],
        )

    def jog(self, robot_name: str, command: str, axis: str, direction: str, step: float) -> int:
        robot = self._robot(robot_name)
        if command.lower() not in {"jog", "move", "cartesian"}:
            return -1
        return int(robot.jog(axis=axis.lower(), direction=direction, step=float(step), vel=20, acc=20))

    def joint_jog(self, robot_name: str, command: str, joint: str, direction: str, step: float) -> int:
        robot = self._robot(robot_name)
        method = getattr(robot, "joint_jog", None) or getattr(robot, "jog_joint", None)
        if not callable(method):
            raise RuntimeError("Twin runtime adapter does not expose joint jogging yet")
        return int(method(joint=joint, direction=direction, step=float(step)))

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
