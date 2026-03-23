import threading

from src.engine.robot.enums.axis import RobotAxis, Direction


class RobotJogService:
    """Application-layer adapter: converts string axis/direction to engine enums and delegates to IRobotService.

    Accepts None robot (robot not connected) — all calls become no-ops.
    """

    def __init__(
        self,
        robot_service=None,
        pose_resolver=None,
        tool_getter=None,
        user_getter=None,
        move_velocity: float = 20.0,
        move_acceleration: float = 10.0,
    ):
        self._robot = robot_service
        self._pose_resolver = pose_resolver
        self._tool_getter = tool_getter
        self._user_getter = user_getter
        self._move_velocity = float(move_velocity)
        self._move_acceleration = float(move_acceleration)
        self._frame_name = ""
        self._lock = threading.Lock()

    def set_frame(self, frame_name: str) -> None:
        self._frame_name = str(frame_name or "").strip()

    def jog(self, axis: str, direction: str, step: float) -> None:
        if self._robot is None:
            return
        try:
            if self._pose_resolver is not None and self._frame_name:
                if not self._lock.acquire(blocking=False):
                    return
                try:
                    current = self._robot.get_current_position()
                    target = self._pose_resolver.resolve(current, axis, direction, step, self._frame_name)
                    if target is not None:
                        tool = int(self._tool_getter()) if self._tool_getter is not None else 0
                        user = int(self._user_getter()) if self._user_getter is not None else 0
                        self._robot.move_ptp(
                            target,
                            tool=tool,
                            user=user,
                            velocity=self._move_velocity,
                            acceleration=self._move_acceleration,
                            wait_to_reach=True,
                        )
                        return
                finally:
                    self._lock.release()
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
