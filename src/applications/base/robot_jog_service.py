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
            servo_linear_speed_mm_s: float = 250.0,
        servo_angular_speed_deg_s: float = 3.0,
        servo_linear_speed_getter: Callable[[], float | None] | None = None,
        servo_angular_speed_getter: Callable[[], float | None] | None = None,
        recovery_servo_linear_speed_getter: Callable[[], float | None] | None = None,
        recovery_servo_angular_speed_getter: Callable[[], float | None] | None = None,
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
        self._recovery_servo_linear_speed_getter = recovery_servo_linear_speed_getter
        self._recovery_servo_angular_speed_getter = recovery_servo_angular_speed_getter
        self._frame_name = ""
        self._active_servo_jog_key: tuple[str, str] | None = None
        self._servo_jog_stop_expected = False
        self._servo_jog_stop_requested = False
        self._recovery_mode = False
        self._lock = threading.Lock()

    def set_recovery_mode(self, enabled: bool) -> None:
        self._recovery_mode = bool(enabled)
        _logger.warning("[JOG] recovery mode %s", "ENABLED" if self._recovery_mode else "disabled")

    def recovery_mode_enabled(self) -> bool:
        return self._recovery_mode

    def set_frame(self, frame_name: str) -> None:
        self._frame_name = str(frame_name or "").strip()

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
            _logger.warning(
                "[JOG] rejected non-numeric step: command=%s axis=%s direction=%s step=%r",
                command,
                axis,
                direction,
                step,
            )
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
            if not self._activate_configured_tool(tool):
                _logger.warning("[JOG] aborted: failed to activate configured tool=%s", tool)
                self._lock.release()
                return
            if not self._activate_configured_workobject(user):
                _logger.warning("[JOG] aborted: failed to activate configured workobject=%s", user)
                self._lock.release()
                return
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
            current = self._robot.get_current_position()
            target = self._resolve_user_frame_target(current, axis, direction, step_value)
            _logger.info(
                "[JOG] mode=configured_user tool=%s user=%s axis=%s direction=%s step=%s current=%s target=%s",
                tool,
                user,
                axis,
                direction,
                step_value,
                current,
                target,
            )
            if target is not None:
                allow_subzero_recovery = (
                    self._recovery_mode
                    and len(current) >= 3
                    and float(current[2]) < 0.0
                    and robot_axis == RobotAxis.Z
                    and robot_direction == Direction.PLUS
                )
                if self._recovery_mode:
                    move_kwargs = {
                        "tool": tool,
                        "user": user,
                        "velocity": self._current_move_velocity(),
                        "acceleration": self._current_move_acceleration(),
                        "blendR": 0.0,
                        "wait_to_reach": True,
                    }
                    if allow_subzero_recovery:
                        move_kwargs["allow_subzero_step_recovery"] = True
                    move_kwargs["allow_collision_recovery"] = True
                    move_kwargs["bypass_safety_limits"] = True
                    self._robot.move_linear(target, **move_kwargs)
                else:
                    outcome = self._robot.move_fast_linear(
                        position=target,
                        tool=tool,
                        user=user,
                        vel=self._current_move_velocity(),
                        acc=self._current_move_acceleration(),
                        trajectory_optimizer="TOTG",
                    )
                    if not self._fast_linear_completed(outcome):
                        _logger.error("[JOG] fast_lin step failed: %s", outcome)
            self._lock.release()
        except Exception:
            _logger.exception(
                "[JOG] failed: command=%s axis=%s direction=%s step=%s",
                command_name,
                axis,
                direction,
                step_value,
            )
            if self._lock.locked():
                self._lock.release()

    @staticmethod
    def _fast_linear_completed(outcome) -> bool:
        return bool(
            isinstance(outcome, dict)
            and outcome.get("result") == 0
            and outcome.get("success") is True
            and outcome.get("accepted") is True
            and outcome.get("final") is True
            and outcome.get("queued") is False
        )

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
        configured_linear_speed = self._current_servo_linear_speed_mm_s()
        configured_angular_speed = self._current_servo_angular_speed_deg_s()
        linear_mm_s = (
            (
                min(requested_speed, configured_linear_speed)
                if requested_speed is not None
                else configured_linear_speed
            )
            if robot_axis.value <= 3
            else None
        )
        angular_deg_s = (
            (
                min(requested_speed, configured_angular_speed)
                if requested_speed is not None
                else configured_angular_speed
            )
            if robot_axis.value > 3
            else None
        )
        if self._recovery_mode:
            if linear_mm_s is not None:
                linear_mm_s = min(
                    linear_mm_s,
                    self._current_positive_float(self._recovery_servo_linear_speed_getter, 25.0),
                )
            if angular_deg_s is not None:
                angular_deg_s = min(
                    angular_deg_s,
                    self._current_positive_float(self._recovery_servo_angular_speed_getter, 5.0),
                )
        if requested_speed is not None:
            applied_speed = linear_mm_s if linear_mm_s is not None else angular_deg_s
            if applied_speed is not None and requested_speed > applied_speed:
                _logger.warning(
                    "[SERVO_JOG] requested speed %.3f capped to configured maximum %.3f",
                    requested_speed,
                    applied_speed,
                )
        result = starter(
            robot_axis,
            robot_direction,
            linear_mm_s=linear_mm_s,
            angular_deg_s=angular_deg_s,
            frame="user",
            tool=tool,
            user=user,
            disable_collision_checking=self._recovery_mode,
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

    def _activate_configured_tool(self, tool: int) -> bool:
        setter = getattr(self._robot, "set_active_tool", None)
        if not callable(setter):
            return True
        return bool(setter(tool))

    def _activate_configured_workobject(self, user: int) -> bool:
        setter = getattr(self._robot, "set_active_workobject", None)
        if not callable(setter):
            return True
        return bool(setter(user))

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

    def _resolve_user_frame_target(self, current_pose, axis: str, direction: str, step: float) -> list[float] | None:
        if not current_pose or len(current_pose) < 6:
            return None
        target = [float(v) for v in current_pose[:6]]
        robot_axis = RobotAxis.get_by_string(axis)
        robot_direction = Direction.get_by_string(direction)
        idx = robot_axis.value - 1
        if idx < 0 or idx >= len(target):
            return None
        target[idx] += robot_direction.value * float(step)
        return target
