import os
from src.engine.hardware.modbus import ModbusConfigSerializer
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
from src.robot_apps.glue.settings.robot import RobotSettingsSerializer


def _build_dashboard_plugin(robot_app):
    from src.plugins.dashboard.dashboard_plugin import DashboardPlugin
    from src.robot_apps.glue.dashboard.glue_dashboard import GlueDashboard
    from src.robot_apps.glue.dashboard.service.glue_dashboard_service import GlueDashboardService

    service = GlueDashboardService(
        robot_service=robot_app.get_service("robot"),
        settings_service=robot_app._settings_service,
    )

    return DashboardPlugin(
        widget_factory=lambda broker: GlueDashboard.create(service=service, broker=broker)
    )



def _build_robot_settings_plugin(robot_app):
    from src.plugins.robot_settings.robot_settings_plugin import RobotSettingsPlugin
    return RobotSettingsPlugin(
        settings_service=robot_app._settings_service,
    )


def _build_glue_settings_plugin(robot_app):
    from src.plugins.glue_settings.glue_settings_plugin import GlueSettingsPlugin
    return GlueSettingsPlugin(
        settings_service=robot_app._settings_service,
    )


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
            PluginSpec(name="DashboardPlugin",     folder_id=1, icon="fa5s.tachometer-alt", factory=_build_dashboard_plugin),
            # PluginSpec(name="RobotSettingsPlugin", folder_id=2, icon="fa5s.robot",          factory=_build_robot_settings_plugin),
            # PluginSpec(name="GlueSettingsPlugin",  folder_id=2, icon="fa5s.sliders-h",      factory=_build_glue_settings_plugin),
        ],
    )

    settings_specs = [
        SettingsSpec("robot_config",  RobotSettingsSerializer(),   "robot/config.json"),
        SettingsSpec("glue_settings", GlueSettingsSerializer(),    "glue/settings.json"),
        SettingsSpec("glue_cells",    GlueCellsConfigSerializer(), "glue/cells.json"),
        SettingsSpec("glue_catalog",  GlueCatalogSerializer(),     "glue/catalog.json"),
        SettingsSpec("modbus_config", ModbusConfigSerializer(),    "hardware/modbus.json"),
    ]

    services = [
        ServiceSpec("robot",      IRobotService,    required=True,  description="Motion and lifecycle control"),
        ServiceSpec("navigation", NavigationService, required=True,  description="Named position movements"),
        ServiceSpec("vision",     VisionService,    required=False, description="Camera-based alignment"),
        ServiceSpec("tools",      IToolService,     required=False, description="Gripper / tool changer"),
    ]

    def on_start(self) -> None:
        self._robot         = self.get_service("robot")
        self._navigation    = self.get_service("navigation")
        self._vision        = self.get_optional_service("vision")
        self._tools         = self.get_optional_service("tools")
        self._robot_config  = self.get_settings("robot_config")
        self._glue_settings = self.get_settings("glue_settings")
        self._glue_cells    = self.get_settings("glue_cells")
        self._glue_catalog  = self.get_settings("glue_catalog")
        self._modbus_config = self.get_settings("modbus_config")
        self._robot.enable_robot()

    def on_stop(self) -> None:
        self._robot.stop_motion()
        self._robot.disable_robot()
