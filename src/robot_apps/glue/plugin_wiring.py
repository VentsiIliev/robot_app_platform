from src.engine.process import ProcessRequirements

# ── Process requirements ──────────────────────────────────────────────────────
# Defined at the app level — the app knows what each of its processes needs.

# TODO need to add health check for the services and not rely on existence only
#  — e.g. if weight cell service is built but fails to connect to any cells, the dashboard should know about it and show a warning instead of just breaking when trying to access the service
_GLUE_PROCESS_REQUIREMENTS  = ProcessRequirements.requires("robot" )
_CLEAN_PROCESS_REQUIREMENTS = ProcessRequirements.requires("robot")


def _build_dashboard_plugin(robot_app):
    from src.plugins.base.widget_plugin import WidgetPlugin
    from src.robot_apps.glue.dashboard.glue_dashboard import GlueDashboard

    robot_service = robot_app.get_service("robot")   # called eagerly

    return WidgetPlugin(
        widget_factory=lambda ms: GlueDashboard.create(
            robot_service     = robot_service,
            settings_service  = robot_app._settings_service,
            messaging_service = ms,
            weight_service    = robot_app.get_optional_service("weight"),
            app_manager       = robot_app.application_manager,
            service_checker   = lambda name: robot_app.get_optional_service(name) is not None,
            requirements      = _GLUE_PROCESS_REQUIREMENTS,
        )
    )


def _build_glue_cell_settings_plugin(robot_app):
    from src.plugins.base.widget_plugin import WidgetPlugin
    from src.plugins.glue_cell_settings import GlueCellSettingsFactory, GlueCellSettingsService

    service = GlueCellSettingsService(
        settings_service = robot_app._settings_service,
        weight_service   = robot_app.get_optional_service("weight"),
    )
    return WidgetPlugin(
        widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms)
    )


def _build_robot_settings_plugin(robot_app):
    from src.plugins.base.widget_plugin import WidgetPlugin
    from src.plugins.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.plugins.robot_settings.service.robot_settings_plugin_service import RobotSettingsPluginService

    service = RobotSettingsPluginService(robot_app._settings_service)
    return WidgetPlugin(widget_factory=lambda _ms: RobotSettingsFactory().build(service))


def _build_glue_settings_plugin(robot_app):
    from src.plugins.base.widget_plugin import WidgetPlugin
    from src.robot_apps.glue.glue_settings import GlueSettingsFactory, GlueSettingsPluginService

    service = GlueSettingsPluginService(robot_app._settings_service)
    return WidgetPlugin(widget_factory=lambda _ms: GlueSettingsFactory().build(service))


def _build_modbus_settings_plugin(robot_app):
    from src.plugins.base.widget_plugin import WidgetPlugin
    from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
    from src.plugins.modbus_settings import ModbusSettingsFactory, ModbusSettingsPluginService

    settings_service = ModbusSettingsPluginService(robot_app._settings_service)
    action_service   = ModbusActionService()
    return WidgetPlugin(
        widget_factory=lambda _ms: ModbusSettingsFactory().build(settings_service, action_service)
    )

