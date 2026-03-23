from __future__ import annotations

from src.engine.robot.height_measuring import RobotSystemHeightMeasuringProvider
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.height_measuring.mock_laser_control import (
    MockLaserControl,
)


class MyRobotSystemHeightMeasuringProvider(RobotSystemHeightMeasuringProvider):
    """Build the system-specific laser-control implementation."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_laser_control(self):
        # TODO: Replace MockLaserControl with the real hardware-backed laser
        # control for this robot system.
        return MockLaserControl()
