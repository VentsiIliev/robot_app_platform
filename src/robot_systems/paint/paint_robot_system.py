import os

from src.engine.common_service_ids import CommonServiceID
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
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
from src.robot_systems.paint import application_wiring
from src.robot_systems.paint.calibration.provider import PaintRobotSystemCalibrationProvider
from src.robot_systems.paint.height_measuring.provider import PaintRobotSystemHeightMeasuringProvider
from src.robot_systems.paint.component_ids import ServiceID
from src.robot_systems.paint.service_builders import build_vacuum_pump_service
from src.robot_systems.paint.targeting.provider import PaintRobotSystemTargetingProvider
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



class PaintRobotSystem(BaseRobotSystem):


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
            id="PAINTING",
            label="Painting",
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
            work_area_id="paint",
            use_height_correction=True,
        ),

    ]

    work_areas = [

        WorkAreaDefinition(
            id="paint",
            label="Paint",
            color="#FF8C32",
            threshold_profile="default",
            supports_detection_roi=True,
            supports_brightness_roi=True,
            supports_height_mapping=True,
        ),
    ]
    work_area_observers = [
        WorkAreaObserverBinding(area_id="paint", movement_group_id="CALIBRATION"),
    ]

    default_active_work_area_id = "paint"

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
            ApplicationSpec(name="PaintDashboard", folder_id=1, icon="fa5s.tachometer-alt",
                            factory=application_wiring._build_dashboard_application),
            ApplicationSpec(name="WorkpieceLibrary", folder_id=4, icon="fa5s.shapes",
                            factory=application_wiring._build_workpiece_library_application),
            ApplicationSpec(name="WorkpieceEditor", folder_id=4, icon="fa5s.draw-polygon",
                            factory=application_wiring._build_paint_contour_editor_application),
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
            ApplicationSpec(name="PickTarget", folder_id=4, icon="fa5s.crosshairs",
                            factory=application_wiring._build_pick_target_application),
        ],
    )

    metadata = SystemMetadata(
        name="PaintSystem",
        version="1.0.0",
        description="Automated edge painting",
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
        ServiceSpec(
            name=ServiceID.VACUUM_PUMP,
            service_type=IVacuumPumpController,
            required=False,
            description="Vacuum pump controller",
            builder=build_vacuum_pump_service,
        ),

    ]

    def on_start(self) -> None:
        from src.robot_systems.paint.applications.dashboard.service.paint_dashboard_service import (
            PaintDashboardService,
        )
        from src.robot_systems.paint.navigation import PaintNavigationService
        from src.robot_systems.paint.processes import PaintProcess
        from src.robot_systems.paint.processes.paint.paint_production_service import PaintProductionService
        from src.robot_systems.paint.processes.paint.workpiece_preparation_service import PaintWorkpiecePreparationService

        self._robot = self.get_service(CommonServiceID.ROBOT)
        _nav_engine = self.get_service(CommonServiceID.NAVIGATION)
        self._work_area_service = self.get_service(CommonServiceID.WORK_AREAS)
        self._vision = self.get_optional_service(CommonServiceID.VISION)
        self._navigation = PaintNavigationService(_nav_engine, vision=self._vision,
                                                 work_area_service=self._work_area_service,
                                                 robot_service=self._robot,
                                                 observed_area_by_group={
                                                     binding.movement_group_id: binding.area_id
                                                     for binding in self.get_work_area_observer_bindings()
                                                 })
        self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
        self._robot_calibration = self.get_settings(CommonSettingsID.ROBOT_CALIBRATION)
        self._paint_targeting = self.get_settings(CommonSettingsID.TARGETING)
        self._targeting_provider = PaintRobotSystemTargetingProvider(self)
        self._vacuum_pump = self.get_optional_service(ServiceID.VACUUM_PUMP)

        if self._vision is not None:
            self._vision.start()
            self.register_managed_resource(self._vision)

        self._height_measuring_provider = PaintRobotSystemHeightMeasuringProvider(self)
        self._height_measuring_service, self._height_measuring_calibration_service, \
            self._laser_detection_service = build_robot_system_height_measuring_services(self)

        self._calibration_provider = PaintRobotSystemCalibrationProvider(self)
        self._calibration_service = build_robot_system_calibration_service(self)

        from src.engine.robot.calibration.robot_calibration_process import RobotCalibrationProcess
        from src.robot_systems.paint.calibration.coordinator import PaintCalibrationCoordinator
        from src.robot_systems.paint.component_ids import ProcessID

        self._calibration_process = RobotCalibrationProcess(
            calibration_service=self._calibration_service,
            messaging=self._messaging_service,
            process_id=ProcessID.ROBOT_CALIBRATION,
            system_manager=self._system_manager,
            service_checker=self.health_registry.check,
        )
        self.register_managed_resource(self._calibration_process)
        self._calibration_coordinator = PaintCalibrationCoordinator(
            calibration_process=self._calibration_process,
            messaging=self._messaging_service,
        )

        self._paint_workpiece_editor_service = application_wiring._build_paint_workpiece_editor_service(self)
        self._paint_capture_snapshot_service = application_wiring._build_capture_snapshot_service(self)
        self._paint_path_preparation_service = application_wiring._build_paint_path_preparation_service(self)
        self._paint_path_executor = application_wiring._build_paint_path_executor(self)
        self._paint_matching_service = application_wiring._build_paint_matching_service(
            self,
            workpiece_service=application_wiring._build_paint_workpiece_service(self),
            capture_snapshot_service=self._paint_capture_snapshot_service,
        )
        self._paint_workpiece_preparation_service = PaintWorkpiecePreparationService(
            can_match_fn=self._paint_matching_service.can_match_saved_workpieces,
            match_workpiece_fn=self._paint_matching_service.match_saved_workpieces,
            transformer=self.get_shared_vision_resolver()[0],
        )
        self._paint_production_service = PaintProductionService(
            workpiece_preparation_service=self._paint_workpiece_preparation_service,
            capture_snapshot_service=self._paint_capture_snapshot_service,
            path_preparation_service=self._paint_path_preparation_service,
            path_executor=self._paint_path_executor,
            vacuum_pump=self._vacuum_pump,
        )
        self._main_process = PaintProcess(
            production_service=self._paint_production_service,
            vacuum_pump=self._vacuum_pump,
            messaging=self._messaging_service,
            system_manager=self._system_manager,
            service_checker=self.health_registry.check,
        )
        self.register_managed_resource(self._main_process)
        self._dashboard_service = PaintDashboardService(self._main_process)

        self._robot.enable_robot()

    def on_stop(self) -> None:
        self._robot.stop_motion()
        self._robot.disable_robot()
