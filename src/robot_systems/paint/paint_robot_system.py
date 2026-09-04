import logging
import os

from src.engine.common_service_ids import CommonServiceID
from src.engine.hardware.dryer.models.dryer_config import DryerConfigSerializer
from src.engine.hardware.dryer.interfaces.i_dryer_service import IDryerService
from src.engine.hardware.fan.interfaces.i_fan_control import IFanControl
from src.engine.hardware.physical_control_buttons.interfaces.i_physical_control_buttons import IPhysicalControlButtons
from src.engine.hardware.peripherals import PeripheralConfigSerializer
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_service import IVacuumSensorService
from src.engine.hardware.communication.modbus.modbus import ModbusConfigSerializer
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
from src.robot_systems.paint import application_wiring, paint_system_config
from src.robot_systems.paint.calibration.provider import PaintRobotSystemCalibrationProvider
from src.robot_systems.paint.height_measuring.provider import PaintRobotSystemHeightMeasuringProvider
from src.robot_systems.paint.component_ids import ServiceID, SettingsID
from src.robot_systems.paint.processes.paint.paint_process_config_serializer import (
    PaintProcessConfigSerializer,
)
from src.robot_systems.paint.service_builders import (
    build_fan_service,
    build_dryer_service,
    build_physical_control_buttons_service,
    build_vacuum_pump_service,
    build_vacuum_sensor_service,
)
from src.robot_systems.paint.targeting.provider import PaintRobotSystemTargetingProvider
from src.robot_systems.paint.applications.dashboard.config import PaintDashboardUiConfig
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

_logger = logging.getLogger(__name__)


def _build_sub_zero_dropoff_corridor(corridor_id, dropoff_pose, dropoff_config):
    """Build the bounded passage corridor for a configured sub-zero Dropoff pose."""
    from src.engine.robot.safety import MotionCorridor

    if dropoff_pose is None or len(dropoff_pose) < 3 or float(dropoff_pose[2]) >= 0.0:
        return None

    dropoff_x, dropoff_y, dropoff_z = (float(value) for value in dropoff_pose[:3])
    x_margin = max(0.1, float(dropoff_config.corridor_x_margin_mm))
    y_margin = max(0.1, float(dropoff_config.corridor_y_margin_mm))
    z_tolerance = max(0.0, float(dropoff_config.corridor_z_tolerance_mm))
    return MotionCorridor(
        corridor_id=corridor_id,
        x_min=dropoff_x - x_margin,
        x_max=dropoff_x + x_margin,
        y_min=dropoff_y - y_margin,
        y_max=dropoff_y + y_margin,
        z_min=dropoff_z - z_tolerance,
        entry_z_max=max(0.0, float(dropoff_config.corridor_entry_z_max_mm)),
        maximum_velocity=max(
            0.1, float(dropoff_config.corridor_maximum_velocity_percent)
        ),
        maximum_acceleration=max(
            0.1, float(dropoff_config.corridor_maximum_acceleration_percent)
        ),
    )


def _build_application_specs():
    """Return the Paint applications enabled by paint_system_config."""
    configured_specs = [
        (paint_system_config.PAINT_DASHBOARD_APP,
         ApplicationSpec(name="PaintDashboard", folder_id=1, icon="fa5s.tachometer-alt",
                         factory=application_wiring._build_dashboard_application)),
        (paint_system_config.WORKPIECE_LIBRARY_APP,
         ApplicationSpec(name="WorkpieceLibrary", folder_id=1, icon="fa5s.shapes",
                         factory=application_wiring._build_workpiece_library_application)),
        (paint_system_config.WORKPIECE_EDITOR_APP,
         ApplicationSpec(name="WorkpieceEditor", folder_id=1, icon="fa5s.draw-polygon",
                         factory=application_wiring._build_paint_contour_editor_application)),
        (paint_system_config.ROBOT_SETTINGS_APP,
         ApplicationSpec(name="RobotSettings", folder_id=2, icon="mdi.robot-industrial",
                         factory=application_wiring._build_robot_settings_application)),
        (paint_system_config.ETHERCAT_DIAGNOSTICS_APP,
         ApplicationSpec(name="EthercatDiagnostics", folder_id=2, icon="fa5s.network-wired",
                         factory=application_wiring._build_ethercat_diagnostics_application)),
        (paint_system_config.MODBUS_SETTINGS_APP,
         ApplicationSpec(name="ModbusSettings", folder_id=2, icon="fa5s.network-wired",
                         factory=application_wiring._build_modbus_settings_application)),
        (paint_system_config.DEVICE_CONTROL_APP,
         ApplicationSpec(name="DeviceControl", folder_id=2, icon="fa5s.sliders-h",
                         factory=application_wiring._build_device_control_application)),
        (paint_system_config.WORK_AREA_SETTINGS_APP,
         ApplicationSpec(name="WorkAreaSettings", folder_id=2, icon="fa5s.vector-square",
                         factory=application_wiring._build_work_area_settings_application)),
        (paint_system_config.CAMERA_SETTINGS_APP,
         ApplicationSpec(name="CameraSettings", folder_id=2, icon="fa5s.camera",
                         factory=application_wiring._build_camera_settings_application)),
        (paint_system_config.CALIBRATION_SETTINGS_APP,
         ApplicationSpec(name="CalibrationSettings", folder_id=2, icon="fa5s.sliders-h",
                         factory=application_wiring._build_calibration_settings_application)),
        (paint_system_config.PAINT_PROCESS_SETTINGS_APP,
         ApplicationSpec(name="PaintProcessSettings", folder_id=2, icon="fa5s.cogs",
                         factory=application_wiring._build_paint_process_settings_application)),
        (paint_system_config.CALIBRATION_APP,
         ApplicationSpec(name="Calibration", folder_id=2, icon="fa5s.crosshairs",
                         factory=application_wiring._build_calibration_application)),
        (paint_system_config.BROKER_DEBUG_APP,
         ApplicationSpec(name="BrokerDebug", folder_id=4, icon="fa5s.project-diagram",
                         factory=application_wiring._build_broker_debug_application)),
        (paint_system_config.USER_MANAGEMENT_APP,
         ApplicationSpec(name="UserManagement", folder_id=3, icon="fa5s.users-cog",
                         factory=application_wiring._build_user_management_application)),
        (paint_system_config.INTRINSIC_CAPTURE_APP,
         ApplicationSpec(name="IntrinsicCapture", folder_id=4, icon="fa5s.camera-retro",
                         factory=application_wiring._build_intrinsic_capture_application)),
        (paint_system_config.HAND_EYE_CALIBRATION_APP,
         ApplicationSpec(name="HandEyeCalibration", folder_id=4, icon="fa5s.hand-paper",
                         factory=application_wiring._build_hand_eye_calibration_application)),
        (paint_system_config.PICK_TARGET_APP,
         ApplicationSpec(name="PickTarget", folder_id=4, icon="fa5s.crosshairs",
                         factory=application_wiring._build_pick_target_application)),
        (paint_system_config.PAINT_MOTION_PLANE_SETUP_APP,
         ApplicationSpec(name="PaintMotionPlaneSetup", folder_id=4, icon="fa5s.compass",
                         factory=application_wiring._build_paint_motion_plane_setup_application)),
        (paint_system_config.PAINT_MOTION_RECIPE_APP,
         ApplicationSpec(name="PaintMotionRecipe", folder_id=4, icon="fa5s.route",
                         factory=application_wiring._build_paint_motion_recipe_application)),
        (paint_system_config.SHAFT_ALIGNMENT_APP,
         ApplicationSpec(name="ShaftAlignment", folder_id=4, icon="fa5s.bullseye",
                         factory=application_wiring._build_shaft_alignment_application)),
    ]
    return [spec for enabled, spec in configured_specs if enabled]


# ── System ───────────────────────────────────────────────────────────────────────



class PaintRobotSystem(BaseRobotSystem):

    ui_config = PaintDashboardUiConfig(
        show_camera_preview=paint_system_config.SHOW_DASHBOARD_CAMERA_PREVIEW,
    )


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
            id="JOG",
            label="Jog",
            group_type=MovementGroupType.VELOCITY_ONLY,
        ),


        MovementGroupDefinition(
            id="Horizontal Shaft",
            label="Horizontal Shaft",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="Vertical Shaft",
            label="Vertical Shaft",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="Vertical Shaft Alignment",
            label="Vertical Shaft Alignment",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="Clean",
            label="Clean",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="Dropoff",
            label="Dropoff",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),
        MovementGroupDefinition(
            id="Magazine",
            label="Magazine",
            group_type=MovementGroupType.SINGLE_POSITION,
            has_trajectory_execution=True,
        ),

        MovementGroupDefinition(
            id="Magazine Fixed Pickup",
            label="Magazine Fixed Pickup",
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
        TargetFrameDefinition(
            name="magazine",
            work_area_id="magazine",
            source_navigation_group="CALIBRATION",
            target_navigation_group="Magazine",
            use_height_correction=True,
        ),
        TargetFrameDefinition(
            name="vertical_shaft_alignment",
            work_area_id="vertical_shaft_alignment",
            source_navigation_group="CALIBRATION",
            target_navigation_group="Vertical Shaft Alignment",
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
        WorkAreaDefinition(
            id="magazine",
            label="Magazine",
            color="#4A90E2",
            threshold_profile="default",
            supports_detection_roi=True,
            supports_brightness_roi=True,
            supports_height_mapping=True,
        ),
        WorkAreaDefinition(
            id="vertical_shaft_alignment",
            label="Vertical Shaft Alignment",
            color="#905BA9",
            threshold_profile="default",
            supports_detection_roi=True,
            supports_brightness_roi=True,
            supports_height_mapping=True,
        ),
    ]
    work_area_observers = [
        WorkAreaObserverBinding(area_id="paint", movement_group_id="CALIBRATION"),
        WorkAreaObserverBinding(area_id="magazine", movement_group_id="Magazine"),
        WorkAreaObserverBinding(
            area_id="vertical_shaft_alignment",
            movement_group_id="Vertical Shaft Alignment",
        ),
    ]

    default_active_work_area_id = ""

    role_policy = RolePolicy(
        role_values=["Admin", "Operator", "Viewer", "Developer"],
        admin_role_value="Admin",
        default_permission_role_values=["Admin"],
        protected_app_role_values={
            "user_management": ["Admin"],
            "paintmotionrecipe": ["Admin", "Developer"],
        },
    )

    shell = ShellSetup(
        folders=[
            FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
            FolderSpec(folder_id=2, name="SERVICE", display_name="Service"),
            FolderSpec(folder_id=3, name="ADMIN", display_name="Administration"),
            FolderSpec(folder_id=4, name="Tests", display_name="Tests"),
        ],
        applications=_build_application_specs(),
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
        SettingsSpec(CommonSettingsID.MODBUS_CONFIG, ModbusConfigSerializer(), "hardware/modbus.json"),
        SettingsSpec(SettingsID.PERIPHERALS, PeripheralConfigSerializer(), "hardware/peripherals.json"),
        SettingsSpec(SettingsID.DRYER_CONFIG, DryerConfigSerializer(), "dryer/settings.json"),
        SettingsSpec(SettingsID.PAINT_PROCESS_CONFIG, PaintProcessConfigSerializer(), "paint/process.json"),
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
        ServiceSpec(
            name=ServiceID.FAN,
            service_type=IFanControl,
            required=False,
            description="Fan controller",
            builder=build_fan_service,
        ),
        ServiceSpec(
            name=ServiceID.PHYSICAL_CONTROL_BUTTONS,
            service_type=IPhysicalControlButtons,
            required=False,
            description="Physical start, pause, and reset buttons",
            builder=build_physical_control_buttons_service,
        ),
        ServiceSpec(
            name=ServiceID.VACUUM_SENSOR,
            service_type=IVacuumSensorService,
            required=False,
            description="Vacuum sensor service",
            builder=build_vacuum_sensor_service,
        ),
        ServiceSpec(
            name=ServiceID.DRYER,
            service_type=IDryerService,
            required=False,
            description="Managed dryer hardware service",
            builder=build_dryer_service,
        ),

    ]

    def _build_pickup_condition(self):
        paint_config = self._paint_process_config_service.get_snapshot()
        pickup_motion = paint_config.pickup_motion
        if bool(pickup_motion.servo_contact_dummy_sensor_enabled):
            from src.engine.robot.procedures import TimedDummyPickupCondition

            _logger.error(
                "[PICKUP] TEST ONLY dummy pickup sensor enabled; "
                "do not use this for production pickup. detect_after_s=%.3f",
                float(pickup_motion.servo_contact_dummy_detect_after_s),
            )
            return TimedDummyPickupCondition(
                detect_after_s=float(pickup_motion.servo_contact_dummy_detect_after_s)
            )
        vacuum_sensor = self.get_optional_service(ServiceID.VACUUM_SENSOR)
        if vacuum_sensor is None:
            _logger.warning(
                "[PICKUP] Vacuum sensor service is unavailable; "
                "servo-contact pickup has no stop condition"
            )
            return None

        from src.engine.robot.procedures import VacuumPickupCondition

        return VacuumPickupCondition(vacuum_sensor)

    def _get_pickup_condition(self):
        self._pickup_condition = self._build_pickup_condition()
        return self._pickup_condition

    def on_start(self) -> None:
        from src.robot_systems.paint.applications.dashboard.service.paint_dashboard_service import (
            PaintDashboardService,
        )
        from src.robot_systems.paint.navigation import PaintNavigationService
        from src.robot_systems.paint.processes import PaintProcess
        from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
        from src.robot_systems.paint.processes.paint.paint_process_config_service import PaintProcessConfigService
        from src.robot_systems.paint.processes.paint.paint_production_service import PaintProductionService

        self._robot = self.get_service(CommonServiceID.ROBOT)
        self.register_managed_resource(self._robot)
        _nav_engine = self.get_service(CommonServiceID.NAVIGATION)
        self._work_area_service = self.get_service(CommonServiceID.WORK_AREAS)
        self._vision = self.get_optional_service(CommonServiceID.VISION)
        self._paint_process_config_service = PaintProcessConfigService(self._settings_service)
        self._navigation = PaintNavigationService(_nav_engine, vision=self._vision,
                                                 work_area_service=self._work_area_service,
                                                 robot_service=self._robot,
                                                 observed_area_by_group={
                                                     binding.movement_group_id: binding.area_id
                                                     for binding in self.get_work_area_observer_bindings()
                                                 },
                                                 unwind_vel_percent=PAINT_PROCESS_CONFIG.navigation_return.unwind_vel_percent,
                                                 unwind_acc_percent=PAINT_PROCESS_CONFIG.navigation_return.unwind_acc_percent,
                                                 unwind_queue_if_busy=PAINT_PROCESS_CONFIG.navigation_return.unwind_queue_if_busy,
                                                 calibration_move_vel_percent=PAINT_PROCESS_CONFIG.navigation_return.calibration_move_vel_percent,
                                                 calibration_move_acc_percent=PAINT_PROCESS_CONFIG.navigation_return.calibration_move_acc_percent,
                                                 calibration_move_motion_type=PAINT_PROCESS_CONFIG.navigation_return.calibration_move_motion_type,
                                                 calibration_move_blendR=PAINT_PROCESS_CONFIG.navigation_return.calibration_move_blendR,
                                                 paint_process_config_service=self._paint_process_config_service)
        self._robot_config = self.get_settings(CommonSettingsID.ROBOT_CONFIG)
        self._dropoff_motion_corridor_id = "workpiece_drop_opening"
        self._paint_process_config_service.add_change_listener(
            self._refresh_dropoff_motion_corridor
        )
        self._refresh_dropoff_motion_corridor(
            self._paint_process_config_service.get_snapshot()
        )
        self._robot_calibration = self.get_settings(CommonSettingsID.ROBOT_CALIBRATION)
        self._paint_targeting = self.get_settings(CommonSettingsID.TARGETING)
        self._targeting_provider = PaintRobotSystemTargetingProvider(self)
        self._vacuum_pump = self.get_optional_service(ServiceID.VACUUM_PUMP)
        self.register_managed_resource(self._vacuum_pump)
        self._fan = self.get_optional_service(ServiceID.FAN)
        self.register_managed_resource(self._fan)
        self._dryer = self.get_optional_service(ServiceID.DRYER)
        self.register_managed_resource(self._dryer)
        self._pickup_condition = self._build_pickup_condition()

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
        self._dryer_release_coordinator = application_wiring._build_dryer_release_coordinator(self)
        if self._dryer_release_coordinator is not None:
            self.register_managed_resource(self._dryer_release_coordinator)
        self._paint_path_executor = application_wiring._build_paint_path_executor(self)
        self._paint_matching_service = application_wiring._build_paint_matching_service(
            self,
            workpiece_service=application_wiring._build_paint_workpiece_service(self),
            capture_snapshot_service=self._paint_capture_snapshot_service,
        )
        self._paint_workpiece_preparation_service = application_wiring._build_paint_workpiece_preparation_service(self)
        self._paint_magazine_load_service = application_wiring._build_paint_magazine_load_service(self)
        self._paint_production_service = PaintProductionService(
            workpiece_preparation_service=self._paint_workpiece_preparation_service,
            capture_snapshot_service=self._paint_capture_snapshot_service,
            path_preparation_service=self._paint_path_preparation_service,
            path_executor=self._paint_path_executor,
            vacuum_pump=self._vacuum_pump,
            paint_process_config_service=self._paint_process_config_service,
            magazine_load_service=self._paint_magazine_load_service,
            navigation_service=self._navigation,
            vision_service=self._vision,
            messaging_service=self._messaging_service,
        )
        self._main_process = PaintProcess(
            production_service=self._paint_production_service,
            robot_service=self._robot,
            vacuum_pump=self._vacuum_pump,
            paint_process_config_service=self._paint_process_config_service,
            messaging=self._messaging_service,
            system_manager=self._system_manager,
            service_checker=self.health_registry.check,
        )
        self.register_managed_resource(self._main_process)
        self._dashboard_service = PaintDashboardService(
            self._main_process,
            capture_snapshot_service=self._paint_capture_snapshot_service,
            path_preparation_service=self._paint_path_preparation_service,
            resolver_getter=lambda: self.get_shared_vision_resolver()[1],
            robot_service=self._robot,
            vision_service=self._vision,
            vacuum_pump=self._vacuum_pump,
            fan_control=self._fan,
            dryer_service=self._dryer,
            persist_dryer_enabled=self._persist_dryer_enabled,
            development_mode=self.development_mode,
            paint_process_config_service=self._paint_process_config_service,
            plate_layout_service=self._paint_path_executor._plate_layout_service,
            target_point_name="camera",
            frame_name="calibration",
        )

        self._robot.enable_robot()

    def _persist_dryer_enabled(self, enabled: bool) -> None:
        from src.engine.hardware.peripherals import PeripheralBinding, PeripheralConfig

        peripheral_config = self._settings_service.get(SettingsID.PERIPHERALS)
        current = peripheral_config.peripherals.get("dryer")
        if current is None:
            raise KeyError("Dryer peripheral is not configured")
        updated = PeripheralBinding(
            slave_id=current.slave_id,
            enabled=bool(enabled),
            inputs=current.inputs,
            outputs=current.outputs,
            commands=current.commands,
            statuses=current.statuses,
        )
        self._settings_service.save(
            SettingsID.PERIPHERALS,
            PeripheralConfig({**peripheral_config.peripherals, "dryer": updated}),
        )

    def _refresh_dropoff_motion_corridor(self, process_config):
        """Replace the registered corridor with values from the live settings snapshot."""
        dropoff_pose = self._navigation.get_group_position("Dropoff")
        dropoff_corridor = _build_sub_zero_dropoff_corridor(
            self._dropoff_motion_corridor_id,
            dropoff_pose,
            process_config.dropoff,
        )
        if dropoff_pose is None or len(dropoff_pose) < 3:
            logging.getLogger(__name__).warning(
                "Dropoff corridor was not registered because movement group 'Dropoff' has no pose"
            )
        elif dropoff_corridor is not None:
            self._robot.register_motion_corridor(dropoff_corridor)

    def on_stop(self) -> None:
        self._robot.stop_motion()
        self._robot.disable_robot()
