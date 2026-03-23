from __future__ import annotations

from src.applications.base.robot_jog_service import RobotJogService


def build_robot_system_jog_service(robot_system, reference_rz_provider=None) -> RobotJogService:
    provider = getattr(robot_system, "get_targeting_provider", lambda: None)()
    if provider is None:
        return RobotJogService(
            robot_service=None,
            frame_options_getter=lambda: [],
            default_frame_getter=lambda: "",
        )

    def _robot_service():
        return getattr(robot_system, "_robot", None)

    def _tool_id() -> int:
        robot_config = getattr(robot_system, "_robot_config", None)
        return int(getattr(robot_config, "robot_tool", 0)) if robot_config is not None else 0

    def _user_id() -> int:
        robot_config = getattr(robot_system, "_robot_config", None)
        return int(getattr(robot_config, "robot_user", 0)) if robot_config is not None else 0

    return RobotJogService(
        robot_service=_robot_service(),
        pose_resolver_getter=lambda: robot_system.build_robot_system_jog_pose_resolver(reference_rz_provider),
        frame_options_getter=provider.get_target_options,
        default_frame_getter=provider.get_default_target_name,
        tool_getter=_tool_id,
        user_getter=_user_id,
    )
