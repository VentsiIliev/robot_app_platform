from __future__ import annotations

from src.robot_systems.base_robot_system import (
    ApplicationSpec,
    BaseRobotSystem,
    FolderSpec,
    RolePolicy,
    ServiceSpec,
    SettingsSpec,
    ShellSetup,
    SystemMetadata,
)
from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT import application_wiring
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.calibration.provider import MyRobotSystemCalibrationProvider
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.height_measuring.provider import (
    MyRobotSystemHeightMeasuringProvider,
)
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.component_ids import ServiceID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.component_ids import SettingsID
from src.robot_systems.ROBOT_SYSTEM_BLUEPRINT.targeting.provider import MyRobotSystemTargetingProvider


class MyRobotSystem(BaseRobotSystem):
    """TODO: Rename to your real robot-system class name."""

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
        ],
        applications=[
            # TODO: Keep only the applications this robot system actually supports.
            ApplicationSpec(
                name="RobotSettings",
                folder_id=2,
                icon="mdi.robot-industrial",
                factory=application_wiring._build_robot_settings_application,
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
        # TODO: Add the generic robot/runtime settings your system needs.
        # SettingsSpec(CommonSettingsID.ROBOT_CONFIG, RobotSettingsSerializer(), "robot/config.json"),
        # SettingsSpec(CommonSettingsID.ROBOT_CALIBRATION, RobotCalibrationSerializer(), "robot/calibration.json"),
        # SettingsSpec(CommonSettingsID.VISION_CAMERA_SETTINGS, CameraSettingsSerializer(), "vision/camera_settings.json"),
        # SettingsSpec(CommonSettingsID.TOOL_CHANGER_CONFIG, ToolChangerSettingsSerializer(), "tools/tool_changer.json"),
        # SettingsSpec(CommonSettingsID.MODBUS_CONFIG, ModbusConfigSerializer(), "hardware/modbus.json"),
        # SettingsSpec(CommonSettingsID.HEIGHT_MEASURING_SETTINGS, HeightMeasuringSettingsSerializer(), "height_measuring/settings.json"),
        # SettingsSpec(CommonSettingsID.HEIGHT_MEASURING_CALIBRATION, HeightMeasuringCalibrationSerializer(), "height_measuring/calibration.json"),
        # SettingsSpec(CommonSettingsID.DEPTH_MAP_DATA, DepthMapDataSerializer(), "height_measuring/depth_map.json"),
        # TODO: Add system-specific settings such as targeting definitions.
        # SettingsSpec(SettingsID.MY_TARGETING, MyTargetingSettingsSerializer(), "targeting/definitions.json"),
    ]

    services = [
        # TODO: Declare required and optional services using service contracts.
        # ServiceSpec(CommonServiceID.ROBOT, IRobotService, required=True, description="Motion and lifecycle control"),
        # ServiceSpec(CommonServiceID.NAVIGATION, NavigationService, required=True, description="Named group navigation"),
        # ServiceSpec(CommonServiceID.VISION, IVisionService, required=False, description="Vision pipeline"),
        # ServiceSpec(CommonServiceID.TOOLS, IToolService, required=False, description="Tool manager"),
        # ServiceSpec(ServiceID.CUSTOM_DEVICE, ICustomDeviceService, required=False, description="System-specific device"),
        # `IVisionService` uses the shared default builder when
        # CommonSettingsID.VISION_CAMERA_SETTINGS is declared.
        # `IToolService` uses the shared default builder when
        # CommonSettingsID.TOOL_CHANGER_CONFIG and CommonSettingsID.ROBOT_CONFIG are declared.
    ]

    def on_start(self) -> None:
        # TODO: Read resolved services and settings into instance attributes.
        # Example:
        # self._robot = self.get_service(CommonServiceID.ROBOT)
        # self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
        #
        # TODO: Install providers here so shared base helpers can use them.
        # Example:
        # self._targeting_provider = MyRobotSystemTargetingProvider(self)
        # self._calibration_provider = MyRobotSystemCalibrationProvider(self)
        # self._height_measuring_provider = MyRobotSystemHeightMeasuringProvider(self)
        #
        # TODO: Build provider-based shared services here when your system supports them.
        # Example:
        # self._calibration_service = build_robot_system_calibration_service(self)
        # (
        #     self._height_measuring_service,
        #     self._height_measuring_calibration_service,
        #     self._laser_detection_service,
        # ) = build_robot_system_height_measuring_services(self)
        raise NotImplementedError("TODO: implement MyRobotSystem.on_start")

    def on_stop(self) -> None:
        # TODO: Shut down runtime services started in on_start().
        raise NotImplementedError("TODO: implement MyRobotSystem.on_stop")
