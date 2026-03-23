from __future__ import annotations

from src.engine.robot.calibration import RobotSystemCalibrationProvider


class MyRobotSystemCalibrationProvider(RobotSystemCalibrationProvider):
    """TODO: Build the system-specific calibration move adapter."""

    def __init__(self, robot_system) -> None:
        self._robot_system = robot_system

    def build_calibration_navigation(self):
        # TODO: Return the adapter or callback object used by the shared
        # calibration builder to move to the CALIBRATION group and apply any
        # system-specific pre-move side effects.
        raise NotImplementedError("TODO: implement build_calibration_navigation")
