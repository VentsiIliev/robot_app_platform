import math
import threading
import logging
from typing import Callable

from src.engine.robot.enums.axis import RobotAxis, Direction

_logger = logging.getLogger(__name__)


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
        move_velocity: float = 10.0,
        move_acceleration: float = 10.0,
        move_velocity_getter: Callable[[], float | None] | None = None,
        move_acceleration_getter: Callable[[], float | None] | None = None,
    ):
        self._robot = robot_service
        self._pose_resolver = pose_resolver
        self._pose_resolver_getter = pose_resolver_getter
        self._frame_options_getter = frame_options_getter
        self._default_frame_getter = default_frame_getter
        self._tool_getter = tool_getter
        self._user_getter = user_getter
        self._default_move_velocity = float(move_velocity)
        self._default_move_acceleration = float(move_acceleration)
        self._move_velocity_getter = move_velocity_getter
        self._move_acceleration_getter = move_acceleration_getter
        self._frame_name = ""
        self._lock = threading.Lock()

    def set_frame(self, frame_name: str) -> None:
        self._frame_name = ""

    def get_available_frames(self) -> list[str]:
        return []

    def get_default_frame(self) -> str:
        return ""

    def jog(self, axis: str, direction: str, step: float) -> None:
        if self._robot is None:
            return
        try:
            if not self._lock.acquire(blocking=False):
                return
            tool = int(self._tool_getter()) if self._tool_getter is not None else 0
            user = int(self._user_getter()) if self._user_getter is not None else 0
            robot_axis = RobotAxis.get_by_string(axis)
            robot_direction = Direction.get_by_string(direction)
            if not self._activate_configured_tool(tool):
                _logger.warning("[JOG] aborted: failed to activate configured tool=%s", tool)
                self._lock.release()
                return
            current = self._robot.get_current_position()
            target = self._resolve_tool_frame_target(current, axis, direction, step)
            _logger.info(
                "[JOG] mode=configured_tool tool=%s axis=%s direction=%s step=%s current=%s target=%s",
                tool,
                axis,
                direction,
                step,
                current,
                target,
            )
            if target is not None:
                velocity = self._current_move_velocity()
                acceleration = self._current_move_acceleration()
                if robot_axis.value > 3:
                    self._robot.start_jog(
                        robot_axis,
                        robot_direction,
                        float(step),
                        velocity,
                        acceleration,
                    )
                else:
                    self._robot.move_ptp(
                        target,
                        tool=tool,
                        user=user,
                        velocity=velocity,
                        acceleration=acceleration,
                        wait_to_reach=True,
                    )
            self._lock.release()
        except Exception:
            if self._lock.locked():
                self._lock.release()
            pass

    def _activate_configured_tool(self, tool: int) -> bool:
        setter = getattr(self._robot, "set_active_tool", None)
        if not callable(setter):
            return True
        return bool(setter(tool))

    def stop_jog(self) -> None:
        if self._robot is None:
            return
        try:
            self._robot.stop_motion()
        except Exception:
            pass

    def _current_move_velocity(self) -> float:
        return self._current_positive_float(self._move_velocity_getter, self._default_move_velocity)

    def _current_move_acceleration(self) -> float:
        return self._current_positive_float(self._move_acceleration_getter, self._default_move_acceleration)

    @staticmethod
    def _current_positive_float(getter, default: float) -> float:
        if callable(getter):
            try:
                value = float(getter())
                if value > 0:
                    return value
            except Exception:
                pass
        return float(default)

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

    def _resolve_tool_frame_target(self, current_pose, axis: str, direction: str, step: float) -> list[float] | None:
        if not current_pose or len(current_pose) < 6:
            return None
        target = [float(v) for v in current_pose[:6]]
        robot_axis = RobotAxis.get_by_string(axis)
        robot_direction = Direction.get_by_string(direction)
        idx = robot_axis.value - 1
        if idx < 0 or idx >= len(target):
            return None
        if idx < 3:
            dx, dy, dz = self._tool_frame_delta(target, idx, robot_direction.value, float(step))
            target[0] += dx
            target[1] += dy
            target[2] += dz
        else:
            target[idx] += robot_direction.value * float(step)
        return target

    @staticmethod
    def _tool_frame_delta(position: list[float], axis_idx: int, direction_value: float, step: float):
        cx, sx = math.cos(math.radians(position[3])), math.sin(math.radians(position[3]))
        cy, sy = math.cos(math.radians(position[4])), math.sin(math.radians(position[4]))
        cz, sz = math.cos(math.radians(position[5])), math.sin(math.radians(position[5]))
        cols = (
            (cy * cz, cy * sz, -sy),
            (cz * sx * sy - cx * sz, cx * cz + sx * sy * sz, cy * sx),
            (cx * cz * sy + sx * sz, cx * sy * sz - cz * sx, cx * cy),
        )
        col = cols[axis_idx]
        scale = direction_value * step
        return col[0] * scale, col[1] * scale, col[2] * scale
