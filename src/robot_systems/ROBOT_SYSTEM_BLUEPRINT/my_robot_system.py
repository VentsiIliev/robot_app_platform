from __future__ import annotations

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.configuration import (
    MovementGroupSettingsSerializer,
    RobotCalibrationSettingsSerializer,
    RobotSettingsSerializer,
    ToolChangerSettingsSerializer,
)
from src.engine.robot.drivers.fairino.test_robot import TestRobotWrapper
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.robot.targeting import TargetingSettingsSerializer
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettingsSerializer
from src.engine.vision.camera_settings_serializer import CameraSettingsSerializer
from src.engine.vision.i_vision_service import IVisionService
from src.engine.work_areas import IWorkAreaService, WorkAreaSettingsSerializer
from src.robot_systems.base_robot_system import BaseRobotSystem
from src.shared_contracts.declarations import (
    ApplicationSpec,
    FolderSpec,
    MovementGroupDefinition,
    MovementGroupType,
    RemoteTcpDefinition,
    RolePolicy,
    ServiceSpec,
    SettingsSpec,
    ShellSetup,
    SystemMetadata,
    TargetFrameDefinition,
    ToolDefinition,
    ToolSlotDefinition,
    WorkAreaDefinition,
    WorkAreaObserverBinding,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT import application_wiring
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.provider import (
    MyRobotSystemTargetingProvider,
)


class MyRobotSystem(BaseRobotSystem):
    """Runnable minimal demo robot system blueprint."""

    tools = [
        ToolDefinition(id=1, name="Single Gripper"),
        ToolDefinition(id=4, name="Double Gripper"),
    ]

    tool_slots = [
        ToolSlotDefinition(
            id=10,
            tool_id=1,
            pickup_movement_group_id="SLOT 10 PICKUP",
            dropoff_movement_group_id="SLOT 10 DROPOFF",
        ),
        ToolSlotDefinition(
            id=11,
            tool_id=4,
            pickup_movement_group_id="SLOT 11 PICKUP",
            dropoff_movement_group_id="SLOT 11 DROPOFF",
        ),
    ]

    movement_groups = [
        MovementGroupDefinition(
            id="LOGIN",
            label="Login",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="HOME",
            label="Home",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="CALIBRATION",
            label="Calibration",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="JOG",
            label="Jog",
            group_type=MovementGroupType.VELOCITY_ONLY,
        ),
        MovementGroupDefinition(
            id="SLOT 10 PICKUP",
            label="Slot 10 Pickup",
            group_type=MovementGroupType.MULTI_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="SLOT 10 DROPOFF",
            label="Slot 10 Dropoff",
            group_type=MovementGroupType.MULTI_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="SLOT 11 PICKUP",
            label="Slot 11 Pickup",
            group_type=MovementGroupType.MULTI_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="SLOT 11 DROPOFF",
            label="Slot 11 Dropoff",
            group_type=MovementGroupType.MULTI_POSITION,
            has_trajectory_execution=True,
        ),
    ]

    target_points = [
        RemoteTcpDefinition(
            name="camera",
            display_name="camera",
        ),
    ]

    target_frames = [
        TargetFrameDefinition(
            name="calibration",
            work_area_id="default",
            use_height_correction=True,
        ),
    ]

    work_areas = [
        WorkAreaDefinition(
            id="default",
            label="Default",
            color="#00CCFF",
            threshold_profile="default",
            supports_detection_roi=True,
            supports_brightness_roi=True,
            supports_height_mapping=True,
        ),
    ]
    work_area_observers = [
        WorkAreaObserverBinding(area_id="default", movement_group_id="CALIBRATION"),
    ]
    default_active_work_area_id = "default"

    role_policy = RolePolicy(
        role_values=["Admin"],
        admin_role_value="Admin",
        default_permission_role_values=["Admin"],
        protected_app_role_values={
            "user_management": ["Admin"],
        },
    )

    shell = ShellSetup(
        folders=[
            FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
            FolderSpec(folder_id=2, name="SERVICE", display_name="Service"),
            FolderSpec(folder_id=3, name="ADMIN", display_name="Administration"),
        ],
        applications=[
            ApplicationSpec(
                name="MyDashboard",
                folder_id=1,
                icon="fa5s.tachometer-alt",
                factory=application_wiring._build_dashboard_application,
            ),
            ApplicationSpec(
                name="WorkAreaSettings",
                folder_id=2,
                icon="fa5s-vector-square",
                factory=application_wiring._build_work_area_settings_application,
            ),
            ApplicationSpec(
                name="CameraSettings",
                folder_id=2,
                icon="fa5s.camera",
                factory=application_wiring._build_camera_settings_application,
            ),
            ApplicationSpec(
                name="CalibrationSettings",
                folder_id=2,
                icon="fa5s.sliders-h",
                factory=application_wiring._build_calibration_settings_application,
            ),
            ApplicationSpec(
                name="RobotSettings",
                folder_id=2,
                icon="mdi.robot-industrial",
                factory=application_wiring._build_robot_settings_application,
            ),
            ApplicationSpec(
                name="ToolSettings",
                folder_id=2,
                icon="fa5s.tools",
                factory=application_wiring._build_tool_settings_application,
            ),
            ApplicationSpec(
                name="UserManagement",
                folder_id=3,
                icon="fa5s.users-cog",
                factory=application_wiring._build_user_management_application,
            ),
        ],
    )

    metadata = SystemMetadata(
        name="MyRobotSystem",
        version="1.0.0",
        description="TODO: Describe the robot system purpose.",
        author="Platform Team",
        settings_root="storage/settings",
    )

    settings_specs = [
        SettingsSpec(
            CommonSettingsID.ROBOT_CONFIG,
            RobotSettingsSerializer(),
            "robot/config.json",
        ),
        SettingsSpec(
            CommonSettingsID.MOVEMENT_GROUPS,
            MovementGroupSettingsSerializer(),
            "robot/movement_groups.json",
        ),
        SettingsSpec(
            CommonSettingsID.ROBOT_CALIBRATION,
            RobotCalibrationSettingsSerializer(),
            "robot/calibration.json",
        ),
        SettingsSpec(
            CommonSettingsID.CALIBRATION_VISION_SETTINGS,
            CalibrationVisionSettingsSerializer(),
            "vision/calibration_settings.json",
        ),
        SettingsSpec(
            CommonSettingsID.VISION_CAMERA_SETTINGS,
            CameraSettingsSerializer(),
            "vision/camera_settings.json",
        ),
        SettingsSpec(
            CommonSettingsID.WORK_AREA_SETTINGS,
            WorkAreaSettingsSerializer(),
            "vision/work_areas.json",
        ),
        SettingsSpec(
            CommonSettingsID.TOOL_CHANGER_CONFIG,
            ToolChangerSettingsSerializer(default_tools=tools, default_slots=tool_slots),
            "tools/tool_changer.json",
        ),
        SettingsSpec(
            CommonSettingsID.TARGETING,
            TargetingSettingsSerializer(),
            "targeting/definitions.json",
        ),
    ]

    services = [
        ServiceSpec(
            CommonServiceID.ROBOT,
            IRobotService,
            required=True,
            description="Shared robot runtime service",
        ),
        ServiceSpec(
            CommonServiceID.NAVIGATION,
            NavigationService,
            required=True,
            description="Shared named-position navigation service",
        ),
        ServiceSpec(
            CommonServiceID.WORK_AREAS,
            IWorkAreaService,
            required=True,
            description="Shared work-area storage and active-area context",
        ),
        ServiceSpec(
            CommonServiceID.VISION,
            IVisionService,
            required=False,
            description="Shared vision pipeline service",
        ),
        ServiceSpec(
            CommonServiceID.TOOLS,
            IToolService,
            required=False,
            description="Shared tool changer runtime service",
        ),
    ]

    def on_start(self) -> None:
        from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.applications.dashboard.service.demo_my_dashboard_service import (
            DemoMyDashboardService,
        )
        from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.processes import DemoProcess

        self._robot = self.get_service(CommonServiceID.ROBOT)
        self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
        self._robot_calibration = self.get_settings(CommonSettingsID.ROBOT_CALIBRATION)
        self._targeting_settings = self.get_settings(CommonSettingsID.TARGETING)
        self._work_area_service = self.get_service(CommonServiceID.WORK_AREAS)
        self._vision = self.get_optional_service(CommonServiceID.VISION)
        self._tools = self.get_optional_service(CommonServiceID.TOOLS)
        self._targeting_provider = MyRobotSystemTargetingProvider(self)
        self._main_process = DemoProcess(
            messaging=self._messaging_service,
            system_manager=self._system_manager,
            service_checker=self.health_registry.check,
        )
        self.register_managed_resource(self._main_process)
        self._dashboard_service = DemoMyDashboardService(self._main_process)
        if self._vision is not None:
            self._vision.start()
            self.register_managed_resource(self._vision)

    def on_stop(self) -> None:
        # Minimal runnable blueprint: nothing explicit to stop.
        pass

    @staticmethod
    def build_demo_robot():
        return TestRobotWrapper()
