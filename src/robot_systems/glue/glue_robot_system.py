import os

from src.engine.common_service_ids import CommonServiceID
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication.modbus.modbus import ModbusConfigSerializer
from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.robot.calibration.service_builders import build_robot_system_calibration_service
from src.engine.robot.configuration import (
    RobotCalibrationSettingsSerializer,
    RobotSettingsSerializer,
    ToolChangerSettingsSerializer,
)
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.height_measuring import build_robot_system_height_measuring_services
from src.engine.robot.height_measuring.depth_map_data import DepthMapDataSerializer
from src.engine.robot.height_measuring.laser_calibration_data import LaserCalibrationDataSerializer
from src.engine.robot.height_measuring.settings import HeightMeasuringSettingsSerializer
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.vision.camera_settings_serializer import CameraSettingsSerializer
from src.engine.vision.i_vision_service import IVisionService


from src.robot_systems.base_robot_system import (
    SystemMetadata, BaseRobotSystem, FolderSpec, ApplicationSpec,
    RolePolicy, ServiceSpec, SettingsSpec, ShellSetup,
)
from src.robot_systems.glue import application_wiring
from src.robot_systems.glue.calibration.provider import GlueRobotSystemCalibrationProvider
from src.robot_systems.glue.component_ids import ServiceID
from src.robot_systems.glue.component_ids import SettingsID
from src.robot_systems.glue.height_measuring.provider import GlueRobotSystemHeightMeasuringProvider
from src.robot_systems.glue.service_builders import build_weight_cell_service, build_motor_service, \
    _build_generator_service
from src.robot_systems.glue.settings.cells import GlueCellsConfigSerializer
from src.robot_systems.glue.settings.device_control import GlueMotorConfigSerializer
from src.robot_systems.glue.settings.glue import GlueSettingsSerializer
from src.robot_systems.glue.settings.glue_types import GlueCatalogSerializer
from src.robot_systems.glue.settings.targeting import GlueTargetingSettingsSerializer
from src.robot_systems.glue.targeting.provider import GlueRobotSystemTargetingProvider


# ── System ───────────────────────────────────────────────────────────────────────

class GlueRobotSystem(BaseRobotSystem):
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
            FolderSpec(folder_id=2, name="SERVICE",    display_name="Service"),
            FolderSpec(folder_id=3, name="ADMIN",      display_name="Administration"),
            FolderSpec(folder_id=4, name="Tests",      display_name="Tests"),
        ],
        applications=[
            ApplicationSpec(name="GlueDashboard",   folder_id=1, icon="fa5s.tachometer-alt",  factory=application_wiring._build_dashboard_application),
            ApplicationSpec(name="RobotSettings",   folder_id=2, icon="mdi.robot-industrial",            factory=application_wiring._build_robot_settings_application),
            ApplicationSpec(name="GlueSettings",    folder_id=2, icon="ph.drop-light",        factory=application_wiring._build_glue_settings_application),
            ApplicationSpec(name="ModbusSettings",  folder_id=2, icon="fa5s.network-wired",    factory=application_wiring._build_modbus_settings_application),
            ApplicationSpec(name="CellSettings",    folder_id=2, icon="fa5s.weight",           factory=application_wiring._build_glue_cell_settings_application),
            ApplicationSpec(name="CameraSettings",  folder_id=2, icon="fa5s.camera",          factory=application_wiring._build_camera_settings_application),
            ApplicationSpec(name="DeviceControl",   folder_id=2, icon="fa5s.sliders-h",       factory=application_wiring._build_device_control_application),
            ApplicationSpec(name="Calibration", folder_id=2, icon="fa5s.crosshairs",          factory=application_wiring._build_calibration_application),
            ApplicationSpec(name="BrokerDebug", folder_id=4, icon="fa5s.project-diagram",       factory=application_wiring._build_broker_debug_application),
            ApplicationSpec(name="WorkpieceEditor", folder_id=1, icon="fa5s.draw-polygon",   factory=application_wiring._build_workpiece_editor_application),
            ApplicationSpec(name="UserManagement", folder_id=3, icon="fa5s.users-cog",        factory=application_wiring._build_user_management_application),
            ApplicationSpec(name="WorkpieceLibrary", folder_id=1, icon="fa5s.book-open",   factory=application_wiring._build_workpiece_library_application),
            ApplicationSpec(name="ToolSettings", folder_id=2, icon="fa5s.tools", factory=application_wiring._build_tool_settings_application),
            ApplicationSpec(name="ContourMatchingTester", folder_id=4, icon="fa6s.shapes",            factory=application_wiring._build_contour_matching_tester),
            ApplicationSpec(name="GlueProcessDriver",     folder_id=4, icon="fa5s.vials",             factory=application_wiring._build_glue_process_driver_application),
            ApplicationSpec(name="HeightMeasuring",       folder_id=4, icon="fa5s.ruler-vertical",   factory=application_wiring._build_height_measuring_application),
            ApplicationSpec(name="PickAndPlaceVisualizer",  folder_id=4, icon="fa5s.map-marked",  factory=application_wiring._build_pick_and_place_visualizer),
            ApplicationSpec(name="PickTarget",              folder_id=4, icon="fa5s.crosshairs",   factory=application_wiring._build_pick_target_application),
        ],
    )

    metadata = SystemMetadata(
        name="GlueSystem",
        version="1.0.0",
        description="Automated glue dispensing vision_service",
        author="Platform Team",
        settings_root=os.path.join("storage", "settings"),
    )


    settings_specs = [
        SettingsSpec(CommonSettingsID.ROBOT_CONFIG,      RobotSettingsSerializer(),             "robot/config.json"),
        SettingsSpec(CommonSettingsID.ROBOT_CALIBRATION, RobotCalibrationSettingsSerializer(),  "robot/calibration.json"),
        SettingsSpec(SettingsID.GLUE_SETTINGS,     GlueSettingsSerializer(),              "glue/settings.json"),
        SettingsSpec(SettingsID.GLUE_TARGETING,    GlueTargetingSettingsSerializer(),     "targeting/definitions.json"),
        SettingsSpec(SettingsID.GLUE_CELLS,        GlueCellsConfigSerializer(),           "glue/cells.json"),
        SettingsSpec(SettingsID.GLUE_CATALOG,      GlueCatalogSerializer(),               "glue/catalog.json"),
        SettingsSpec(CommonSettingsID.MODBUS_CONFIG,     ModbusConfigSerializer(),              "hardware/modbus.json"),
        SettingsSpec(CommonSettingsID.VISION_CAMERA_SETTINGS,     CameraSettingsSerializer(),         "vision/camera_settings.json"),
        SettingsSpec(CommonSettingsID.TOOL_CHANGER_CONFIG,          ToolChangerSettingsSerializer(),         "tools/tool_changer.json"),
        SettingsSpec(CommonSettingsID.HEIGHT_MEASURING_SETTINGS,    HeightMeasuringSettingsSerializer(),     "height_measuring/settings.json"),
        SettingsSpec(CommonSettingsID.HEIGHT_MEASURING_CALIBRATION, LaserCalibrationDataSerializer(),        "height_measuring/calibration_data.json"),
        SettingsSpec(CommonSettingsID.DEPTH_MAP_DATA,               DepthMapDataSerializer(),                "height_measuring/depth_map.json"),
        SettingsSpec(SettingsID.GLUE_MOTOR_CONFIG,            GlueMotorConfigSerializer(),             "hardware/motors.json"),
    ]

    services = [
        ServiceSpec(CommonServiceID.ROBOT, IRobotService, required=True, description="Motion and lifecycle control"),
        ServiceSpec(CommonServiceID.NAVIGATION, NavigationService, required=True, description="Named position movements"),
        ServiceSpec(CommonServiceID.VISION, IVisionService, required=False, description="Camera-based alignment",
                    ),
        ServiceSpec(
            name=ServiceID.WEIGHT,
            service_type=IWeightCellService,
            required=True,
            description="Multi-cell weight monitoring",
            builder=build_weight_cell_service,
        ),
        ServiceSpec(
            name=ServiceID.MOTOR,
            service_type=IMotorService,
            required=True,
            description="Glue pump motor service",
            builder=build_motor_service,
        ),
        ServiceSpec(
            name=CommonServiceID.TOOLS,
            service_type=IToolService,
            required=False,
            description="Gripper / tool changer",
        ),
    ]

    def on_start(self) -> None:
        from src.robot_systems.glue.navigation import GlueNavigationService
        self._robot = self.get_service(CommonServiceID.ROBOT)
        _nav_engine      = self.get_service(CommonServiceID.NAVIGATION)
        self._vision = self.get_optional_service(CommonServiceID.VISION)
        self._navigation = GlueNavigationService(_nav_engine, vision=self._vision, robot_service=self._robot)  # ← typed facade
        self._tools = self.get_optional_service(CommonServiceID.TOOLS)
        self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
        self._robot_calibration = self.get_settings(CommonSettingsID.ROBOT_CALIBRATION)
        self._glue_settings = self.get_settings(SettingsID.GLUE_SETTINGS)
        self._glue_targeting = self.get_settings(SettingsID.GLUE_TARGETING)
        self._glue_cells = self.get_settings(SettingsID.GLUE_CELLS)
        self._glue_catalog = self.get_settings(SettingsID.GLUE_CATALOG)
        self._modbus_config = self.get_settings(CommonSettingsID.MODBUS_CONFIG)
        self._targeting_provider = GlueRobotSystemTargetingProvider(self)
        self._height_measuring_provider = GlueRobotSystemHeightMeasuringProvider(self)
        self._weight = self.get_service(ServiceID.WEIGHT)
        self._vision = self.get_optional_service(CommonServiceID.VISION)

        self._weight.start_monitoring(
            cell_ids=self._glue_cells.get_all_cell_ids(),
            interval_s=0.5,
        )
        self._vision.start()
        self._motor = self.get_service(ServiceID.MOTOR)
        self._motor.open()

        self._height_measuring_service, self._height_measuring_calibration_service, \
            self._laser_detection_service = build_robot_system_height_measuring_services(self)

        self._calibration_provider = GlueRobotSystemCalibrationProvider(self)
        self._calibration_service = build_robot_system_calibration_service(self)
        self._generator           = _build_generator_service(self)

        self._coordinator         = self._build_coordinator()

        self._robot.enable_robot()

    def on_stop(self) -> None:

        self._weight.stop_monitoring()
        self._weight.disconnect_all()

        self._robot.stop_motion()
        self._robot.disable_robot()

        self._motor.close()

    # ── Coordinator ───────────────────────────────────────────────────────────

    @property
    def coordinator(self):
        return self._coordinator

    def _build_coordinator(self):
        from src.engine.process.process_requirements import ProcessRequirements
        from src.robot_systems.glue.processes.robot_calibration_process import RobotCalibrationProcess
        from src.robot_systems.glue.processes.clean_process import CleanProcess
        from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator
        from src.robot_systems.glue.processes.glue_process import GlueProcess
        from src.robot_systems.glue.processes.glue_dispensing.dispensing_config import GlueDispensingConfig
        from src.robot_systems.glue.service_builders import GlueCellTypeResolver
        from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess
        from src.robot_systems.glue.processes.pick_and_place.config import PickAndPlaceConfig
        from src.robot_systems.glue.domain.glue_job_builder_service import GlueJobBuilderService
        from src.robot_systems.glue.domain.glue_job_execution_service import GlueJobExecutionService
        from src.robot_systems.glue.domain.matching.matching_service import MatchingService
        from src.engine.vision.capture_snapshot_service import CaptureSnapshotService
        from src.robot_systems.glue.domain.workpieces.repository.json_workpiece_repository import \
            JsonWorkpieceRepository
        from src.robot_systems.glue.domain.workpieces.service.workpiece_service import WorkpieceService
        glue_requirements = ProcessRequirements.requires(CommonServiceID.ROBOT, ServiceID.MOTOR, CommonServiceID.VISION)
        pick_and_place_requirements = ProcessRequirements.requires(CommonServiceID.ROBOT, CommonServiceID.VISION)
        clean_requirements = ProcessRequirements.requires(CommonServiceID.ROBOT)
        calibration_requirements = ProcessRequirements.requires(CommonServiceID.ROBOT, CommonServiceID.VISION)
        service_checker = self.health_registry.check

        vision_service = self.get_optional_service(CommonServiceID.VISION)
        tool_service = self.get_optional_service(CommonServiceID.TOOLS)
        height_service = self._height_measuring_service
        capture_snapshot_service = CaptureSnapshotService(
            vision_service=vision_service,
            robot_service=self._robot,
        )
        transformer, glue_resolver = self.get_shared_vision_resolver()
        matching_service = MatchingService(
            vision_service=vision_service,
            workpiece_service=WorkpieceService(JsonWorkpieceRepository(self.workpieces_storage_path())),
            capture_snapshot_service=capture_snapshot_service,
        ) if vision_service else None
        glue_process = GlueProcess(
            robot_service=self._robot,
            motor_service=self._motor,
            resolver=GlueCellTypeResolver(self._glue_cells),
            config=GlueDispensingConfig(
                robot_tool=self._robot_config.robot_tool,
                robot_user=self._robot_config.robot_user,
            ),
            navigation_service=self._navigation,
            generator=self._generator,
            messaging=self._messaging_service,
            system_manager=self._system_manager,
            requirements=glue_requirements,
            service_checker=service_checker,
        )
        execution_service = (
            GlueJobExecutionService(
                matching_service=matching_service,
                job_builder=GlueJobBuilderService(
                    transformer=transformer,
                    resolver=glue_resolver,
                    z_min=float(self._robot_config.safety_limits.z_min),
                ),
                glue_process=glue_process,
                navigation_service=self._navigation,
                vision_service=vision_service,
                capture_snapshot_service=capture_snapshot_service,
                messaging_service=self._messaging_service,
            )
            if matching_service is not None else None
        )

        return GlueOperationCoordinator(
            glue_process=glue_process,
            pick_and_place_process=PickAndPlaceProcess(
                robot_service=self._robot,
                navigation_service=self._navigation,
                messaging=self._messaging_service,
                matching_service=matching_service,
                tool_service=tool_service,
                height_service=height_service,
                resolver=glue_resolver,
                config=PickAndPlaceConfig(
                    camera_to_tcp_x_offset=float(self._robot_config.camera_to_tcp_x_offset),
                    camera_to_tcp_y_offset=float(self._robot_config.camera_to_tcp_y_offset),
                ),
                system_manager=self._system_manager,
                requirements=pick_and_place_requirements,
                service_checker=service_checker,
            ),
            clean_process=CleanProcess(
                robot_service=self._robot,
                messaging=self._messaging_service,
                system_manager=self._system_manager,
                requirements=clean_requirements,
                service_checker=service_checker,
            ),
            calibration_process=RobotCalibrationProcess(
                calibration_service=self._calibration_service,
                messaging=self._messaging_service,
                system_manager=self._system_manager,
                requirements=calibration_requirements,
                service_checker=service_checker,
            ),
            messaging=self._messaging_service,
            execution_service=execution_service,
            settings_service=self._settings_service,
        )
