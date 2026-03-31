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
        pose_resolver_getter=None,
        frame_options_getter=None,
        default_frame_getter=None,
        tool_getter=None,
        user_getter=None,
        move_velocity: float = 20.0,
        move_acceleration: float = 10.0,
    ):
        self._robot = robot_service
        self._pose_resolver = pose_resolver
        self._pose_resolver_getter = pose_resolver_getter
        self._frame_options_getter = frame_options_getter
        self._default_frame_getter = default_frame_getter
        self._tool_getter = tool_getter
        self._user_getter = user_getter
        self._move_velocity = float(move_velocity)
        self._move_acceleration = float(move_acceleration)
        self._frame_name = ""
        self._lock = threading.Lock()

    def set_frame(self, frame_name: str) -> None:
        self._frame_name = str(frame_name or "").strip()

    def get_available_frames(self) -> list[str]:
        if callable(self._frame_options_getter):
            try:
                return list(self._frame_options_getter())
            except Exception:
                return []
        resolver = self._current_pose_resolver()
        available_frames = getattr(resolver, "available_frames", None)
        if callable(available_frames):
            try:
                return list(available_frames())
            except Exception:
                return []
        return []

    def get_default_frame(self) -> str:
        if callable(self._default_frame_getter):
            try:
                value = str(self._default_frame_getter() or "").strip()
                if value:
                    return value
            except Exception:
                pass
        frames = self.get_available_frames()
        return frames[0] if frames else ""

    def jog(self, axis: str, direction: str, step: float) -> None:
        if self._robot is None:
            return
        try:
            if not self._lock.acquire(blocking=False):
                return
            if self._prefers_incremental_jog():
                try:
                    self._robot.start_jog(
                        RobotAxis.get_by_string(axis),
                        Direction.get_by_string(direction),
                        step,
                    )
                    return
                finally:
                    self._lock.release()

            resolver = self._current_pose_resolver()
            point = self._current_frame_point(resolver)
            if resolver is not None and point is not None:
                try:
                    current = self._robot.get_current_position()
                    target = resolver.resolve(current, axis, direction, step, point)
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
                    return
            self._robot.start_jog(
                RobotAxis.get_by_string(axis),
                Direction.get_by_string(direction),
                step,
            )
            self._lock.release()
        except Exception:
            if self._lock.locked():
                self._lock.release()
            pass

    def stop_jog(self) -> None:
        if self._robot is None:
            return
        try:
            self._robot.stop_motion()
        except Exception:
            pass

    def _current_pose_resolver(self):
        if callable(self._pose_resolver_getter):
            try:
                return self._pose_resolver_getter()
            except Exception:
                return None
        return self._pose_resolver

    def _current_frame_point(self, resolver):
        if resolver is None:
            return None
        frame_name = self._frame_name or self.get_default_frame()
        point_for_name = getattr(resolver, "point_for_name", None)
        if callable(point_for_name) and frame_name:
            try:
                return point_for_name(frame_name)
            except Exception:
                return None
        return None

    def _prefers_incremental_jog(self) -> bool:
        robot = getattr(self._robot, "_robot", None)
        prefers_incremental = getattr(robot, "prefers_incremental_jog", None)
        if callable(prefers_incremental):
            try:
                return bool(prefers_incremental())
            except Exception:
                return False
        return False
