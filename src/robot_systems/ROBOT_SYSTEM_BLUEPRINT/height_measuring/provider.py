from __future__ import annotations

from src.engine.robot.height_measuring import RobotSystemHeightMeasuringProvider


class MyRobotSystemHeightMeasuringProvider(RobotSystemHeightMeasuringProvider):
    """TODO: Build the system-specific laser-control implementation."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_laser_control(self):
        # TODO: Return the laser-control implementation used by the shared
        # height-measuring builder.
        raise NotImplementedError("TODO: implement build_laser_control")
