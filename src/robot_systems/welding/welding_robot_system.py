import os

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.calibration.service_builders import build_robot_system_calibration_service
from src.engine.robot.configuration import (
    MovementGroupSettingsSerializer,
    RobotCalibrationSettingsSerializer,
    RobotSettingsSerializer,
)
from src.engine.robot.height_measuring import (
    HeightMeasuringSettingsSerializer,
    LaserCalibrationDataSerializer,
    build_robot_system_height_measuring_services,
)
from src.engine.robot.height_measuring.depth_map_data import DepthMapDataSerializer
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.targeting import TargetingSettingsSerializer
from src.engine.vision.calibration_vision_settings import CalibrationVisionSettingsSerializer
from src.engine.vision.camera_settings_serializer import CameraSettingsSerializer
from src.engine.vision.i_vision_service import IVisionService
from src.engine.work_areas import IWorkAreaService, WorkAreaSettingsSerializer
from src.robot_systems.base_robot_system import BaseRobotSystem
from src.robot_systems.welding import application_wiring
from src.robot_systems.welding.calibration.provider import WeldingRobotSystemCalibrationProvider
from src.robot_systems.welding.height_measuring.provider import WeldingRobotSystemHeightMeasuringProvider
from src.robot_systems.welding.targeting.provider import WeldingRobotSystemTargetingProvider
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
    WorkAreaDefinition,
    WorkAreaObserverBinding,
)


# ── System ───────────────────────────────────────────────────────────────────────



class WeldingRobotSystem(BaseRobotSystem):


    movement_groups = [

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
            id="CAMERA_CALIBRATION",
            label="Camera Calibration",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),

        MovementGroupDefinition(
            id="JOG",
            label="Jog",
            group_type=MovementGroupType.VELOCITY_ONLY,
        ),

        MovementGroupDefinition(
            id="WELDINGING",
            label="Weldinging",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
         ),

    ]

    target_points = [
        RemoteTcpDefinition(
            name="camera",
            display_name="camera",
        ),
        RemoteTcpDefinition(
            name="tool",
            display_name="tool",
        ),

    ]

    target_frames = [
        TargetFrameDefinition(
            name="calibration",
            work_area_id="welding",
            use_height_correction=True,
        ),

    ]

    work_areas = [

        WorkAreaDefinition(
            id="welding",
            label="Welding",
            color="#FF8C32",
            threshold_profile="default",
            supports_detection_roi=True,
            supports_brightness_roi=True,
            supports_height_mapping=True,
        ),
    ]
    work_area_observers = [
        WorkAreaObserverBinding(area_id="welding", movement_group_id="CALIBRATION"),
    ]

    default_active_work_area_id = "welding"

    role_policy = RolePolicy(
        role_values=["Admin", "Operator", "Viewer", "Developer"],
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
            FolderSpec(folder_id=4, name="Tests", display_name="Tests"),
        ],
        applications=[
            ApplicationSpec(name="WeldingDashboard", folder_id=1, icon="fa5s.tachometer-alt",
                            factory=application_wiring._build_dashboard_application),
            ApplicationSpec(name="WeldingContourEditor", folder_id=1, icon="fa5s.draw-polygon",
                            factory=application_wiring._build_welding_contour_editor_application),
            ApplicationSpec(name="RobotSettings", folder_id=2, icon="mdi.robot-industrial",
                            factory=application_wiring._build_robot_settings_application),
            ApplicationSpec(name="WorkAreaSettings", folder_id=2, icon="fa5s-vector-square",
                            factory=application_wiring._build_work_area_settings_application),
            ApplicationSpec(name="CameraSettings", folder_id=2, icon="fa5s.camera",
                            factory=application_wiring._build_camera_settings_application),
            ApplicationSpec(name="CalibrationSettings", folder_id=2, icon="fa5s.sliders-h",
                            factory=application_wiring._build_calibration_settings_application),
            ApplicationSpec(name="Calibration", folder_id=2, icon="fa5s.crosshairs",
                            factory=application_wiring._build_calibration_application),
            ApplicationSpec(name="BrokerDebug", folder_id=4, icon="fa5s.project-diagram",
                            factory=application_wiring._build_broker_debug_application),
            ApplicationSpec(name="UserManagement", folder_id=3, icon="fa5s.users-cog",
                            factory=application_wiring._build_user_management_application),
            ApplicationSpec(name="IntrinsicCapture", folder_id=4, icon="fa5s.camera-retro",
                            factory=application_wiring._build_intrinsic_capture_application),
            ApplicationSpec(name="HandEyeCalibration", folder_id=4, icon="fa5s.hand-paper",
                            factory=application_wiring._build_hand_eye_calibration_application),
        ],
    )

    metadata = SystemMetadata(
        name="WeldingSystem",
        version="1.0.0",
        description="Automated edge weldinging",
        author="Platform Team",
        settings_root=os.path.join("storage", "settings"),
    )

    settings_specs = [
        SettingsSpec(CommonSettingsID.ROBOT_CONFIG, RobotSettingsSerializer(), "robot/config.json"),
        SettingsSpec(CommonSettingsID.MOVEMENT_GROUPS, MovementGroupSettingsSerializer(), "robot/movement_groups.json"),
        SettingsSpec(CommonSettingsID.ROBOT_CALIBRATION, RobotCalibrationSettingsSerializer(),
                     "robot/calibration.json"),
        SettingsSpec(CommonSettingsID.TARGETING, TargetingSettingsSerializer(), "targeting/definitions.json"),

        SettingsSpec(
            CommonSettingsID.CALIBRATION_VISION_SETTINGS,
            CalibrationVisionSettingsSerializer(),
            "vision/calibration_settings.json",
        ),
        SettingsSpec(CommonSettingsID.VISION_CAMERA_SETTINGS, CameraSettingsSerializer(),
                     "vision/camera_settings.json"),
        SettingsSpec(CommonSettingsID.WORK_AREA_SETTINGS, WorkAreaSettingsSerializer(), "vision/work_areas.json"),
        SettingsSpec(CommonSettingsID.HEIGHT_MEASURING_SETTINGS, HeightMeasuringSettingsSerializer(),
                     "height_measuring/settings.json"),
        SettingsSpec(CommonSettingsID.HEIGHT_MEASURING_CALIBRATION, LaserCalibrationDataSerializer(),
                     "height_measuring/calibration_data.json"),
        SettingsSpec(CommonSettingsID.DEPTH_MAP_DATA, DepthMapDataSerializer(), "height_measuring/depth_map.json"),
    ]

    services = [
        ServiceSpec(CommonServiceID.ROBOT, IRobotService, required=True, description="Motion and lifecycle control"),
        ServiceSpec(CommonServiceID.NAVIGATION, NavigationService, required=True,
                    description="Named position movements"),
        ServiceSpec(CommonServiceID.WORK_AREAS, IWorkAreaService, required=True,
                    description="Shared work-area storage and active-area context"),
        ServiceSpec(CommonServiceID.VISION, IVisionService, required=False, description="Camera-based alignment",
                    ),

    ]

    def on_start(self) -> None:
        from src.robot_systems.welding.applications.dashboard.service.welding_dashboard_service import (
            WeldingDashboardService,
        )
        from src.robot_systems.welding.navigation import WeldingNavigationService
        from src.robot_systems.welding.processes import WeldingProcess

        self._robot = self.get_service(CommonServiceID.ROBOT)
        _nav_engine = self.get_service(CommonServiceID.NAVIGATION)
        self._work_area_service = self.get_service(CommonServiceID.WORK_AREAS)
        self._vision = self.get_optional_service(CommonServiceID.VISION)
        self._navigation = WeldingNavigationService(_nav_engine, vision=self._vision,
                                                 work_area_service=self._work_area_service,
                                                 robot_service=self._robot,
                                                 observed_area_by_group={
                                                     binding.movement_group_id: binding.area_id
                                                     for binding in self.get_work_area_observer_bindings()
                                                 })
        self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
        self._robot_calibration = self.get_settings(CommonSettingsID.ROBOT_CALIBRATION)
        self._welding_targeting = self.get_settings(CommonSettingsID.TARGETING)
        self._targeting_provider = WeldingRobotSystemTargetingProvider(self)

        if self._vision is not None:
            self._vision.start()
            self.register_managed_resource(self._vision)

        self._height_measuring_provider = WeldingRobotSystemHeightMeasuringProvider(self)
        self._height_measuring_service, self._height_measuring_calibration_service, \
            self._laser_detection_service = build_robot_system_height_measuring_services(self)

        self._calibration_provider = WeldingRobotSystemCalibrationProvider(self)
        self._calibration_service = build_robot_system_calibration_service(self)

        from src.engine.robot.calibration.robot_calibration_process import RobotCalibrationProcess
        from src.robot_systems.welding.calibration.coordinator import WeldingCalibrationCoordinator
        from src.robot_systems.welding.component_ids import ProcessID

        self._calibration_process = RobotCalibrationProcess(
            calibration_service=self._calibration_service,
            messaging=self._messaging_service,
            process_id=ProcessID.ROBOT_CALIBRATION,
            system_manager=self._system_manager,
            service_checker=self.health_registry.check,
        )
        self.register_managed_resource(self._calibration_process)
        self._calibration_coordinator = WeldingCalibrationCoordinator(
            calibration_process=self._calibration_process,
            messaging=self._messaging_service,
        )

        self._main_process = WeldingProcess(
            messaging=self._messaging_service,
            system_manager=self._system_manager,
            service_checker=self.health_registry.check,
        )
        self.register_managed_resource(self._main_process)
        self._dashboard_service = WeldingDashboardService(self._main_process)

        self._robot.enable_robot()

    def on_stop(self) -> None:
        self._robot.stop_motion()
        self._robot.disable_robot()


