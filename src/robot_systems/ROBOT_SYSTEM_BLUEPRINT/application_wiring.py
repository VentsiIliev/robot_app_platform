from __future__ import annotations

from src.applications.base.widget_application import WidgetApplication
from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.component_ids import SettingsID


def _build_dashboard_application(robot_system):
    from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard import (
        MyDashboardFactory,
    )

    return WidgetApplication(
        widget_factory=lambda ms: MyDashboardFactory().build(
            robot_system._dashboard_service,
            messaging=ms,
        )
    )


def _build_user_management_application(robot_system):
    from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
    from src.applications.user_management.service.user_management_application_service import (
        UserManagementApplicationService,
    )
    from src.applications.user_management.user_management_factory import UserManagementFactory
    from src.engine.auth.authorization_service import AuthorizationService
    from src.engine.auth.json_permissions_repository import JsonPermissionsRepository
    from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.domain.users import build_my_user_schema

    role_policy = robot_system.__class__.role_policy
    service = UserManagementApplicationService(
        CsvUserRepository(
            robot_system.users_storage_path(),
            build_my_user_schema(role_policy.role_values),
        )
    )
    permissions_service = AuthorizationService(
        JsonPermissionsRepository(
            robot_system.permissions_storage_path(),
            default_role_values=role_policy.default_permission_role_values,
        ),
        protected_app_role_values=role_policy.protected_app_role_values,
    )
    known_ids = [spec.app_id for spec in robot_system.shell.applications]

    return WidgetApplication(
        widget_factory=lambda ms: UserManagementFactory().build(
            service,
            permissions_service,
            known_ids,
            role_values=role_policy.role_values,
            default_role_values=role_policy.default_permission_role_values,
            messaging=ms,
        )
    )


def _build_robot_settings_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import (
        RobotSettingsApplicationService,
    )
    from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.settings_adapter import (
        from_editor_dict,
        to_editor_dict,
    )

    def _save_targeting_definitions(data) -> None:
        robot_system._settings_service.save(
            CommonSettingsID.TARGETING,
            from_editor_dict(
                data,
                robot_system._settings_service.get(CommonSettingsID.TARGETING),
                robot_system.get_target_point_definitions(),
                robot_system.get_target_frame_definitions(),
            ),
        )
        robot_system.invalidate_shared_vision_resolver()

    service = RobotSettingsApplicationService(
        robot_system._settings_service,
        config_key=CommonSettingsID.ROBOT_CONFIG,
        movement_groups_key=CommonSettingsID.MOVEMENT_GROUPS,
        calibration_key=CommonSettingsID.ROBOT_CALIBRATION,
        robot_service=robot_system.get_optional_service(CommonServiceID.ROBOT),
        navigation_service=robot_system.get_service(CommonServiceID.NAVIGATION),
        load_targeting_definitions_fn=lambda: to_editor_dict(
            robot_system._settings_service.get(CommonSettingsID.TARGETING),
            robot_system.get_target_point_definitions(),
            robot_system.get_target_frame_definitions(),
        ),
        save_targeting_definitions_fn=_save_targeting_definitions,
        movement_group_definitions=robot_system.get_movement_group_definitions(),
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: RobotSettingsFactory(
            movement_group_definitions=robot_system.get_movement_group_definitions()
        ).build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_camera_settings_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.camera_settings.camera_settings_factory import (
        CameraSettingsFactory,
    )
    from src.applications.camera_settings.service.camera_settings_application_service import (
        CameraSettingsApplicationService,
    )

    service = CameraSettingsApplicationService(
        settings_service=robot_system._settings_service,
        vision_service=robot_system.get_service(CommonServiceID.VISION),
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: CameraSettingsFactory().build(
            service,
            ms,
            jog_service=jog_service,
        )
    )


def _build_work_area_settings_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.work_area_settings.service.work_area_settings_application_service import (
        WorkAreaSettingsApplicationService,
    )
    from src.applications.work_area_settings.work_area_settings_factory import (
        WorkAreaSettingsFactory,
    )

    service = WorkAreaSettingsApplicationService(
        work_area_service=robot_system.get_service(CommonServiceID.WORK_AREAS),
        vision_service=robot_system.get_optional_service(CommonServiceID.VISION),
    )
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: WorkAreaSettingsFactory(
            work_area_definitions=robot_system.get_work_area_definitions()
        ).build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


def _build_tool_settings_application(robot_system):
    from src.applications.base.robot_jog_service_builder import build_robot_system_jog_service
    from src.applications.tool_settings import (
        ToolSettingsApplicationService,
        ToolSettingsFactory,
    )

    service = ToolSettingsApplicationService(robot_system._settings_service)
    jog_service = build_robot_system_jog_service(robot_system)
    return WidgetApplication(
        widget_factory=lambda ms: ToolSettingsFactory().build(
            service,
            messaging=ms,
            jog_service=jog_service,
        )
    )


# TODO: Add more `_build_<application>()` functions as your robot system grows.
# Prefer shared platform applications such as RobotSettings whenever your
# robot system adopts the common contracts they expect.
