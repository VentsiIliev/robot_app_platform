from __future__ import annotations

from src.engine.robot.height_measuring import RobotSystemHeightMeasuringProvider
from src.robot_systems.paint.height_measuring.mock_laser_control import (
    MockLaserControl,
)


class PaintRobotSystemHeightMeasuringProvider(RobotSystemHeightMeasuringProvider):

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_laser_control(self):
        return MockLaserControl()

