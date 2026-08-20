from __future__ import annotations

from src.applications.base.robot_jog_service import RobotJogService
from src.engine.common_settings_ids import CommonSettingsID


_JOG_GROUP_ID = "JOG"
_DEFAULT_JOG_VELOCITY = 10.0
_DEFAULT_JOG_ACCELERATION = 10.0
_DEFAULT_SERVO_LINEAR_MM_S = 10.0
_DEFAULT_SERVO_ANGULAR_DEG_S = 3.0


def build_robot_system_jog_service(robot_system, reference_rz_provider=None) -> RobotJogService:
    def _robot_service():
        return getattr(robot_system, "_robot", None)

    def _current_robot_config():
        settings_service = getattr(robot_system, "_settings_service", None)
        getter = getattr(settings_service, "get", None)
        if callable(getter):
            try:
                config = getter(CommonSettingsID.ROBOT_CONFIG)
                if config is not None:
                    return config
            except Exception:
                pass
        return getattr(robot_system, "_robot_config", None)

    def _tool_id() -> int:
        robot_config = _current_robot_config()
        return int(getattr(robot_config, "robot_tool", 0)) if robot_config is not None else 0

    def _user_id() -> int:
        robot_config = _current_robot_config()
        return int(getattr(robot_config, "robot_user", 0)) if robot_config is not None else 0

    def _jog_group():
        settings_service = getattr(robot_system, "_settings_service", None)
        if settings_service is None:
            return None
        try:
            settings = settings_service.get(CommonSettingsID.MOVEMENT_GROUPS)
        except Exception:
            return None
        groups = getattr(settings, "movement_groups", {}) or {}
        return groups.get(_JOG_GROUP_ID)

    def _jog_group_value(name: str, default: float) -> float:
        group = _jog_group()
        if group is None:
            return default
        try:
            value = float(getattr(group, name))
        except (AttributeError, TypeError, ValueError):
            return default
        return value if value > 0 else default

    return RobotJogService(
        robot_service=_robot_service(),
        tool_getter=_tool_id,
        user_getter=_user_id,
        move_velocity=_DEFAULT_JOG_VELOCITY,
        move_acceleration=_DEFAULT_JOG_ACCELERATION,
        move_velocity_getter=lambda: _jog_group_value("velocity", _DEFAULT_JOG_VELOCITY),
        move_acceleration_getter=lambda: _jog_group_value("acceleration", _DEFAULT_JOG_ACCELERATION),
        servo_linear_speed_mm_s=_DEFAULT_SERVO_LINEAR_MM_S,
        servo_angular_speed_deg_s=_DEFAULT_SERVO_ANGULAR_DEG_S,
        servo_linear_speed_getter=lambda: _jog_group_value(
            "servo_linear_mm_s",
            _DEFAULT_SERVO_LINEAR_MM_S,
        ),
        servo_angular_speed_getter=lambda: _jog_group_value(
            "servo_angular_deg_s",
            _DEFAULT_SERVO_ANGULAR_DEG_S,
        ),
    )
