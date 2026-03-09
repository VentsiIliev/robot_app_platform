from src.engine.robot.enums.axis import RobotAxis, Direction


class RobotJogService:
    """Application-layer adapter: converts string axis/direction to engine enums and delegates to IRobotService.

    Accepts None robot (robot not connected) — all calls become no-ops.
    """

    def __init__(self, robot_service=None):
        self._robot = robot_service

    def jog(self, axis: str, direction: str, step: float) -> None:
        if self._robot is None:
            return
        try:
            self._robot.start_jog(
                RobotAxis.get_by_string(axis),
                Direction.get_by_string(direction),
                step,
            )
        except Exception:
            pass

    def stop_jog(self) -> None:
        if self._robot is None:
            return
        try:
            self._robot.stop_motion()
        except Exception:
            pass
