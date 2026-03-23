from __future__ import annotations

from src.engine.common_settings_ids import CommonSettingsID


def _build_robot_settings_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import (
        RobotSettingsApplicationService,
    )
    from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.component_ids import SettingsID
    from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.settings_adapter import (
        from_editor_dict,
        to_editor_dict,
    )

    service = RobotSettingsApplicationService(
        robot_system._settings_service,
        config_key=CommonSettingsID.ROBOT_CONFIG,  # TODO: replace if not used
        calibration_key=CommonSettingsID.ROBOT_CALIBRATION,  # TODO: replace/remove if not used
        targeting_key=SettingsID.MY_TARGETING,  # TODO: replace/remove if not used
        targeting_to_editor=to_editor_dict,
        targeting_from_editor=from_editor_dict,
    )

    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: RobotSettingsFactory().build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


# TODO: Add one `_build_<application>()` function per application registered in
# `MyRobotSystem.shell.applications`.
#
# Rules:
# - use `robot_system.get_shared_vision_resolver()` when an application needs
#   image-target -> robot-pose conversion
# - use `build_robot_system_jog_service(robot_system, ...)` for shared jog wiring
# - the generic Robot Settings application can edit system targeting definitions
#   when you pass `targeting_key`, `targeting_to_editor`, and `targeting_from_editor`
# - use `robot_system.workpieces_storage_path()` / `users_storage_path()` /
#   `permissions_storage_path()` instead of hardcoded package paths
