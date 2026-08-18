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
        servo_linear_speed_mm_s: float = 10.0,
        servo_angular_speed_deg_s: float = 3.0,
        servo_linear_speed_getter: Callable[[], float | None] | None = None,
        servo_angular_speed_getter: Callable[[], float | None] | None = None,
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
        self._default_servo_linear_speed_mm_s = float(servo_linear_speed_mm_s)
        self._default_servo_angular_speed_deg_s = float(servo_angular_speed_deg_s)
        self._servo_linear_speed_getter = servo_linear_speed_getter
        self._servo_angular_speed_getter = servo_angular_speed_getter
        self._frame_name = ""
        self._active_servo_jog_key: tuple[str, str] | None = None
        self._servo_jog_stop_expected = False
        self._servo_jog_stop_requested = False
        self._lock = threading.Lock()

    def set_frame(self, frame_name: str) -> None:
        self._frame_name = ""

    def get_available_frames(self) -> list[str]:
        return []

    def get_default_frame(self) -> str:
        return ""

    def jog(self, command: str, axis: str | None = None, direction: str | None = None, step: float | None = None) -> None:
        if self._robot is None:
            return
        command_name = str(command).strip().upper()
        if command_name not in {"JOG_ROBOT", "SERVO_JOG"}:
            command, axis, direction, step = "JOG_ROBOT", command, axis, direction
            command_name = "JOG_ROBOT"
        if axis is None or direction is None or step is None:
            return
        try:
            step_value = float(step)
        except (TypeError, ValueError):
            return
        try:
            if not self._lock.acquire(blocking=False):
                return
            tool = int(self._tool_getter()) if self._tool_getter is not None else 0
            user = int(self._user_getter()) if self._user_getter is not None else 0
            robot_axis = RobotAxis.get_by_string(axis)
            robot_direction = Direction.get_by_string(direction)
            _logger.info(
                "[JOG] request command=%s axis=%s direction=%s step=%s tool=%s user=%s",
                command_name,
                axis,
                direction,
                step_value,
                tool,
                user,
            )
            if command_name == "SERVO_JOG":
                self._servo_jog_stop_expected = True
                self._servo_jog_stop_requested = False
                self._try_start_servo_jog(
                    robot_axis,
                    robot_direction,
                    axis,
                    direction,
                    tool,
                    user,
                    speed_value=step_value,
                )
                self._lock.release()
                return
            if not self._activate_configured_tool(tool):
                _logger.warning("[JOG] aborted: failed to activate configured tool=%s", tool)
                self._lock.release()
                return
            current = self._robot.get_current_position()
            target = self._resolve_tool_frame_target(current, axis, direction, step_value)
            _logger.info(
                "[JOG] mode=configured_tool tool=%s axis=%s direction=%s step=%s current=%s target=%s",
                tool,
                axis,
                direction,
                step_value,
                current,
                target,
            )
            if target is not None:
                self._robot.move_linear(
                    target,
                    tool=tool,
                    user=user,
                    velocity=self._current_move_velocity(),
                    acceleration=self._current_move_acceleration(),
                    blendR=0.0,
                    wait_to_reach=True,
                )
            self._lock.release()
        except Exception:
            if self._lock.locked():
                self._lock.release()
            pass

    def joint_jog(
        self,
        command: str,
        joint: str | None = None,
        direction: str | None = None,
        step: float | None = None,
    ) -> None:
        if self._robot is None:
            return
        command_name = str(command).strip().upper()
        if command_name != "JOG_JOINT":
            command, joint, direction, step = "JOG_JOINT", command, joint, direction
            command_name = "JOG_JOINT"
        if joint is None or direction is None or step is None:
            return
        try:
            step_value = float(step)
        except (TypeError, ValueError):
            return
        try:
            if not self._lock.acquire(blocking=False):
                return
            robot_direction = Direction.get_by_string(direction)
            starter = getattr(self._robot, "start_joint_jog", None)
            if not callable(starter):
                _logger.warning("[JOINT_JOG] unsupported by robot service")
                self._lock.release()
                return
            result = starter(
                joint,
                robot_direction,
                step_value,
                velocity=self._current_move_velocity(),
                acceleration=self._current_move_acceleration(),
            )
            _logger.info(
                "[JOINT_JOG] request command=%s joint=%s direction=%s step=%s result=%s",
                command_name,
                joint,
                direction,
                step_value,
                result,
            )
            self._lock.release()
        except Exception:
            if self._lock.locked():
                self._lock.release()
            pass

    def _try_start_servo_jog(
        self,
        robot_axis: RobotAxis,
        robot_direction: Direction,
        axis_name: str,
        direction_name: str,
        tool: int,
        user: int,
        speed_value: float | None = None,
    ) -> None:
        starter = getattr(self._robot, "start_servo_jog", None)
        if not callable(starter):
            return

        key = (str(axis_name).upper(), str(direction_name).upper())
        if self._active_servo_jog_key == key:
            return
        if self._active_servo_jog_key is not None:
            self.stop_jog()
            self._servo_jog_stop_expected = True

        requested_speed = self._positive_float_or_none(speed_value)
        linear_mm_s = (
            requested_speed or self._current_servo_linear_speed_mm_s()
            if robot_axis.value <= 3
            else None
        )
        angular_deg_s = (
            requested_speed or self._current_servo_angular_speed_deg_s()
            if robot_axis.value > 3
            else None
        )
        servo_direction = self._step_compatible_servo_direction(
            robot_axis,
            robot_direction,
        )
        if servo_direction is not robot_direction:
            _logger.info(
                "[SERVO_JOG] remapped direction for Step-compatible semantics: "
                "axis=%s requested=%s servo=%s",
                axis_name,
                robot_direction.name,
                servo_direction.name,
            )
        result = starter(
            robot_axis,
            servo_direction,
            linear_mm_s=linear_mm_s,
            angular_deg_s=angular_deg_s,
            frame="user",
            tool=tool,
            user=user,
        )
        if result == 0:
            if self._servo_jog_stop_requested:
                stopper = getattr(self._robot, "stop_servo_jog", None)
                if callable(stopper):
                    stopper()
                self._active_servo_jog_key = None
                self._servo_jog_stop_expected = False
                self._servo_jog_stop_requested = False
                _logger.info("[SERVO_JOG] start completed after release; stopped immediately")
                return
            self._active_servo_jog_key = key
            _logger.debug(
                "[SERVO_JOG] started axis=%s direction=%s linear_mm_s=%s angular_deg_s=%s tool=%s user=%s",
                axis_name,
                direction_name,
                linear_mm_s,
                angular_deg_s,
                tool,
                user,
            )
            return

        if result == -404:
            _logger.warning("[SERVO_JOG] unsupported by runtime")
            return

        _logger.warning("[SERVO_JOG] rejected result=%s", result)

    @staticmethod
    def _step_compatible_servo_direction(
        axis: RobotAxis,
        direction: Direction,
    ) -> Direction:
        if axis == RobotAxis.Y:
            return Direction.MINUS if direction == Direction.PLUS else Direction.PLUS
        return direction

    def _activate_configured_tool(self, tool: int) -> bool:
        setter = getattr(self._robot, "set_active_tool", None)
        if not callable(setter):
            return True
        return bool(setter(tool))

    def stop_jog(self) -> None:
        if self._robot is None:
            return
        try:
            if self._active_servo_jog_key is not None or self._servo_jog_stop_expected:
                had_active_servo = self._active_servo_jog_key is not None
                self._servo_jog_stop_requested = True
                stopper = getattr(self._robot, "stop_servo_jog", None)
                if callable(stopper):
                    stopper()
                self._active_servo_jog_key = None
                self._servo_jog_stop_expected = False
                if had_active_servo:
                    self._servo_jog_stop_requested = False
                return
            self._robot.stop_motion()
        except Exception:
            self._active_servo_jog_key = None
            self._servo_jog_stop_expected = False
            self._servo_jog_stop_requested = False
            pass

    def _current_move_velocity(self) -> float:
        return self._current_positive_float(self._move_velocity_getter, self._default_move_velocity)

    def _current_move_acceleration(self) -> float:
        return self._current_positive_float(self._move_acceleration_getter, self._default_move_acceleration)

    def _current_servo_linear_speed_mm_s(self) -> float:
        return self._current_positive_float(
            self._servo_linear_speed_getter,
            self._default_servo_linear_speed_mm_s,
        )

    def _current_servo_angular_speed_deg_s(self) -> float:
        return self._current_positive_float(
            self._servo_angular_speed_getter,
            self._default_servo_angular_speed_deg_s,
        )

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

    @staticmethod
    def _positive_float_or_none(value) -> float | None:
        try:
            parsed = abs(float(value))
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

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
