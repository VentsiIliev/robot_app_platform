import os

from src.engine.process import ProcessRequirements
from src.engine.hardware.communication.modbus.modbus import ModbusConfigSerializer
from src.engine.hardware.weight.interfaces.i_weight_cell_service import IWeightCellService
from src.engine.robot.features.navigation_service import NavigationService
from src.engine.robot.interfaces.i_robot_service import IRobotService
from src.engine.robot.interfaces.i_tool_service import IToolService
from src.engine.vision.vision_service import VisionService
from src.robot_apps.base_robot_app import (
    AppMetadata, BaseRobotApp, FolderSpec, PluginSpec,
    ServiceSpec, SettingsSpec, ShellSetup,
)
from src.robot_apps.glue.settings.cells import GlueCellsConfigSerializer
from src.robot_apps.glue.settings.glue import GlueSettingsSerializer
from src.robot_apps.glue.settings.glue_types import GlueCatalogSerializer
from src.engine.robot.configuration import RobotSettingsSerializer, RobotCalibrationSettingsSerializer
from src.robot_apps.glue import plugin_wiring

# ── Service builders ──────────────────────────────────────────────────────────

def _build_weight_cell_service(ctx):
    from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
    cells_config = ctx.settings.get("glue_cells")   # GlueCellsConfig — all cells
    return build_http_weight_cell_service(
        cells_config = cells_config,
        messaging    = ctx.messaging_service,
    )


# ── App ───────────────────────────────────────────────────────────────────────

class GlueRobotApp(BaseRobotApp):

    metadata = AppMetadata(
        name="GlueApplication",
        version="1.0.0",
        description="Automated glue dispensing application",
        author="Platform Team",
        settings_root=os.path.join("storage", "settings"),
    )

    shell = ShellSetup(
        folders=[
            FolderSpec(folder_id=1, name="PRODUCTION", display_name="Production"),
            FolderSpec(folder_id=2, name="SERVICE",    display_name="Service"),
            FolderSpec(folder_id=3, name="ADMIN",      display_name="Administration"),
        ],
        plugins=[
            PluginSpec(name="GlueDashboard",   folder_id=1, icon="fa5s.tachometer-alt",  factory=plugin_wiring._build_dashboard_plugin),
            PluginSpec(name="RobotSettings",   folder_id=2, icon="fa5s.robot",            factory=plugin_wiring._build_robot_settings_plugin),
            PluginSpec(name="GlueSettings",    folder_id=2, icon="fa5s.sliders-h",        factory=plugin_wiring._build_glue_settings_plugin),
            PluginSpec(name="ModbusSettings",  folder_id=2, icon="fa5s.network-wired",    factory=plugin_wiring._build_modbus_settings_plugin),
            PluginSpec(name="CellSettings", folder_id=2, icon="fa5s.weight", factory=plugin_wiring._build_glue_cell_settings_plugin),

        ],
    )

    settings_specs = [
        SettingsSpec("robot_config",      RobotSettingsSerializer(),             "robot/config.json"),
        SettingsSpec("robot_calibration", RobotCalibrationSettingsSerializer(),  "robot/calibration.json"),
        SettingsSpec("glue_settings",     GlueSettingsSerializer(),              "glue/settings.json"),
        SettingsSpec("glue_cells",        GlueCellsConfigSerializer(),           "glue/cells.json"),
        SettingsSpec("glue_catalog",      GlueCatalogSerializer(),               "glue/catalog.json"),
        SettingsSpec("modbus_config",     ModbusConfigSerializer(),              "hardware/modbus.json"),
    ]

    services = [
        ServiceSpec("robot",       IRobotService,      required=True,  description="Motion and lifecycle control"),
        ServiceSpec("navigation",  NavigationService,  required=True,  description="Named position movements"),
        ServiceSpec("vision",      VisionService,      required=False, description="Camera-based alignment"),
        ServiceSpec("tools",       IToolService,       required=False, description="Gripper / tool changer"),
        ServiceSpec(
            name         = "weight",
            service_type = IWeightCellService,
            required     = True,
            description  = "Multi-cell weight monitoring",
            builder      = _build_weight_cell_service,
        ),
    ]

    def on_start(self) -> None:
        self._robot = self.get_service("robot")
        self._navigation = self.get_service("navigation")
        self._vision = self.get_optional_service("vision")
        self._tools = self.get_optional_service("tools")
        self._robot_config = self.get_settings("robot_config")
        self._robot_calibration = self.get_settings("robot_calibration")
        self._glue_settings = self.get_settings("glue_settings")
        self._glue_cells = self.get_settings("glue_cells")
        self._glue_catalog = self.get_settings("glue_catalog")
        self._modbus_config = self.get_settings("modbus_config")
        self._weight = self.get_service("weight")

        self._weight.start_monitoring(
            cell_ids=self._glue_cells.get_all_cell_ids(),
            interval_s=0.5,
        )

        self._robot.enable_robot()

    def on_stop(self) -> None:

        self._weight.stop_monitoring()
        self._weight.disconnect_all()

        self._robot.stop_motion()
        self._robot.disable_robot()
