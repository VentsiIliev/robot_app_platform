from __future__ import annotations

import os

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.robot.services.robot_service import RobotService
from src.engine.robot.services.robot_state_manager import RobotStateManager
from src.engine.robot.services.robot_state_publisher import RobotStatePublisher
from src.engine.robot.tool_changer import ToolChanger
from src.engine.robot.tool_manager import ToolManager
from src.engine.vision.i_vision_service import IVisionService
from src.engine.work_areas import IWorkAreaService, WorkAreaService


def build_robot_service(ctx) -> IRobotService:
    publisher = RobotStatePublisher(ctx.messaging_service)
    state = RobotStateManager(ctx.robot.clone(), publisher=publisher)
    state.start_monitoring()
    return RobotService(motion=ctx.motion, robot=ctx.robot, state_provider=state)


def build_navigation_service(ctx) -> NavigationService:
    return NavigationService(
        motion=ctx.motion,
        robot_config_key=CommonSettingsID.ROBOT_CONFIG,
        movement_groups_key=CommonSettingsID.MOVEMENT_GROUPS,
        settings_service=ctx.settings,
    )


def build_tool_service(ctx):
    """Build the standard tool service from common tool and robot settings."""

    tc_settings = ctx.settings.get(CommonSettingsID.TOOL_CHANGER_CONFIG)
    robot_config = ctx.settings.get(CommonSettingsID.ROBOT_CONFIG)
    movement_groups = ctx.settings.get(CommonSettingsID.MOVEMENT_GROUPS)
    if not movement_groups.movement_groups and getattr(robot_config, "movement_groups", None):
        movement_groups.movement_groups = dict(robot_config.movement_groups)
        ctx.settings.save(CommonSettingsID.MOVEMENT_GROUPS, movement_groups)
    tool_changer = ToolChanger(slots=tc_settings.slots, tools=tc_settings.tools)

    return ToolManager(
        motion_service=ctx.motion,
        tool_changer=tool_changer,
        robot_config=robot_config,
        movement_groups=movement_groups,
        slot_definitions=ctx.system_class.tool_slots,
    )


def build_vision_service(ctx):
    """Build the standard vision service from common camera settings."""

    from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
    from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service
    from src.engine.vision.vision_service import VisionService

    settings_repo = ctx.settings.get_repo(CommonSettingsID.VISION_CAMERA_SETTINGS)
    data_storage_path = ctx.system_class.storage_path("settings", "vision", "data")
    os.makedirs(data_storage_path, exist_ok=True)

    service = Service(
        data_storage_path=data_storage_path,
        settings_file_path=settings_repo.file_path,
    )
    work_area_service = ctx.services.get(CommonServiceID.WORK_AREAS)
    vision_system = VisionSystem(
        storage_path=data_storage_path,
        messaging_service=ctx.messaging_service,
        service=service,
        work_area_service=work_area_service,
    )
    return VisionService(vision_system, work_area_service=work_area_service)


def build_work_area_service(ctx) -> IWorkAreaService:
    return WorkAreaService(
        settings_service=ctx.settings,
        definitions=ctx.system_class.work_areas,
        default_active_area_id=ctx.system_class.default_active_work_area_id,
    )


DEFAULT_SERVICE_BUILDERS = {
    IRobotService: build_robot_service,
    NavigationService: build_navigation_service,
    IWorkAreaService: build_work_area_service,
    IToolService: build_tool_service,
    IVisionService: build_vision_service,
}
