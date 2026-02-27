import os

from src.robot_systems.glue.settings_ids import SettingsID
from src.engine.process import ProcessRequirements
from src.engine.hardware.communication.modbus.modbus import ModbusConfigSerializer
from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.vision.vision_service import VisionService
from src.robot_systems.base_robot_system import (
    SystemMetadata, BaseRobotSystem, FolderSpec, ApplicationSpec,
    ServiceSpec, SettingsSpec, ShellSetup,
)
from src.robot_systems.glue.settings.cells import GlueCellsConfigSerializer
from src.robot_systems.glue.settings.glue import GlueSettingsSerializer
from src.robot_systems.glue.settings.glue_types import GlueCatalogSerializer
from src.engine.robot.configuration import RobotSettingsSerializer, RobotCalibrationSettingsSerializer
from src.robot_systems.glue import application_wiring
from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.robot_systems.glue.service_ids import ServiceID


# ── Service builders ──────────────────────────────────────────────────────────

def _build_weight_cell_service(ctx):
    from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
    cells_config = ctx.settings.get(SettingsID.GLUE_CELLS)   # GlueCellsConfig — all cells
    return build_http_weight_cell_service(
        cells_config = cells_config,
        messaging    = ctx.messaging_service,
    )


def _build_motor_service(ctx):
    from src.engine.hardware.motor.modbus.modbus_motor_factory import build_modbus_motor_service
    from src.engine.hardware.motor.models.motor_config import MotorConfig
    from src.robot_systems.glue.motor.glue_motor_error_decoder import GlueMotorErrorDecoder
    modbus_config = ctx.settings.get(SettingsID.MODBUS_CONFIG)
    return build_modbus_motor_service(
        modbus_config = modbus_config,
        motor_config  = MotorConfig(
            health_check_trigger_register = 17,
            motor_error_count_register    = 20,
            motor_error_registers_start   = 21,
            motor_addresses               = [0, 2, 4, 6],   # 4 glue pump motors
            address_to_error_prefix       = {0: 1, 2: 2, 4: 3, 6: 4},
        ),
        error_decoder = GlueMotorErrorDecoder(),
    )


# ── System ───────────────────────────────────────────────────────────────────────

class GlueRobotSystem(BaseRobotSystem):

    metadata = SystemMetadata(
        name="GlueSystem",
        version="1.0.0",
        description="Automated glue dispensing system",
        author="Platform Team",
        settings_root=os.path.join("storage", "settings"),
    )

    shell = ShellSetup(
        folders=[
            FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
            FolderSpec(folder_id=2, name="SERVICE",    display_name="Service"),
            FolderSpec(folder_id=3, name="ADMIN",      display_name="Administration"),
        ],
        applications=[
            ApplicationSpec(name="GlueDashboard",   folder_id=1, icon="fa5s.tachometer-alt",  factory=application_wiring._build_dashboard_application),
            ApplicationSpec(name="RobotSettings",   folder_id=2, icon="fa5s.robot",            factory=application_wiring._build_robot_settings_application),
            ApplicationSpec(name="GlueSettings",    folder_id=2, icon="fa5s.sliders-h",        factory=application_wiring._build_glue_settings_application),
            ApplicationSpec(name="ModbusSettings",  folder_id=2, icon="fa5s.network-wired",    factory=application_wiring._build_modbus_settings_application),
            ApplicationSpec(name="CellSettings", folder_id=2, icon="fa5s.weight", factory=application_wiring._build_glue_cell_settings_application),

        ],
    )

    settings_specs = [
        SettingsSpec(SettingsID.ROBOT_CONFIG,      RobotSettingsSerializer(),             "robot/config.json"),
        SettingsSpec(SettingsID.ROBOT_CALIBRATION, RobotCalibrationSettingsSerializer(),  "robot/calibration.json"),
        SettingsSpec(SettingsID.GLUE_SETTINGS,     GlueSettingsSerializer(),              "glue/settings.json"),
        SettingsSpec(SettingsID.GLUE_CELLS,        GlueCellsConfigSerializer(),           "glue/cells.json"),
        SettingsSpec(SettingsID.GLUE_CATALOG,      GlueCatalogSerializer(),               "glue/catalog.json"),
        SettingsSpec(SettingsID.MODBUS_CONFIG,     ModbusConfigSerializer(),              "hardware/modbus.json"),
    ]

    services = [
        ServiceSpec(ServiceID.ROBOT,       IRobotService,      required=True,  description="Motion and lifecycle control"),
        ServiceSpec(ServiceID.NAVIGATION,  NavigationService,  required=True,  description="Named position movements"),
        ServiceSpec(ServiceID.VISION,      VisionService,      required=False, description="Camera-based alignment"),
        ServiceSpec(ServiceID.TOOLS,       IToolService,       required=False, description="Gripper / tool changer"),
        ServiceSpec(
            name         = ServiceID.WEIGHT,
            service_type = IWeightCellService,
            required     = True,
            description  = "Multi-cell weight monitoring",
            builder      = _build_weight_cell_service,
        ),
        ServiceSpec(
            name         = ServiceID.MOTOR,
            service_type = IMotorService,
            required     = True,
            description  = "Glue pump motor service",
            builder      = _build_motor_service,
        ),
    ]


    def on_start(self) -> None:
        self._robot = self.get_service(ServiceID.ROBOT)
        self._navigation = self.get_service(ServiceID.NAVIGATION)
        self._vision = self.get_optional_service(ServiceID.VISION)
        self._tools = self.get_optional_service(ServiceID.TOOLS)
        self._robot_config = self.get_settings(SettingsID.ROBOT_CONFIG)
        self._robot_calibration = self.get_settings(SettingsID.ROBOT_CALIBRATION)
        self._glue_settings = self.get_settings(SettingsID.GLUE_SETTINGS)
        self._glue_cells = self.get_settings(SettingsID.GLUE_CELLS)
        self._glue_catalog = self.get_settings(SettingsID.GLUE_CATALOG)
        self._modbus_config = self.get_settings(SettingsID.MODBUS_CONFIG)
        self._weight = self.get_service(ServiceID.WEIGHT)

        self._weight.start_monitoring(
            cell_ids=self._glue_cells.get_all_cell_ids(),
            interval_s=0.5,
        )

        self._motor = self.get_service(ServiceID.MOTOR)
        self._motor.open()

        self._coordinator = self._build_coordinator()

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
        from src.robot_systems.glue.processes.clean_process import CleanProcess
        from src.robot_systems.glue.processes.glue_operation_coordinator import GlueOperationCoordinator
        from src.robot_systems.glue.processes.glue_process import GlueProcess
        from src.robot_systems.glue.processes.pick_and_place_process import PickAndPlaceProcess

        glue_process_requirements    = ProcessRequirements.requires(ServiceID.ROBOT,ServiceID.MOTOR,ServiceID.VISION)
        pick_and_place_process_requirements = ProcessRequirements.requires(ServiceID.ROBOT, ServiceID.VISION)
        clean_process_requirements = ProcessRequirements.requires(ServiceID.ROBOT)


        service_checker = self.health_registry.check

        return GlueOperationCoordinator(
            glue_process = GlueProcess(
                robot_service   = self._robot,
                messaging       = self._messaging_service,
                system_manager  = self._system_manager,
                requirements    = glue_process_requirements,
                service_checker = service_checker,
            ),
            pick_and_place_process = PickAndPlaceProcess(
                robot_service   = self._robot,
                messaging       = self._messaging_service,
                system_manager  = self._system_manager,
                requirements    = pick_and_place_process_requirements,
                service_checker = service_checker,
            ),
            clean_process = CleanProcess(
                robot_service   = self._robot,
                messaging       = self._messaging_service,
                system_manager  = self._system_manager,
                requirements    = clean_process_requirements,
                service_checker = service_checker,
            ),
            messaging = self._messaging_service,
        )
