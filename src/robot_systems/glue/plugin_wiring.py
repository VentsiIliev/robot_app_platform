from src.engine.process import ProcessRequirements
from src.engine.process.service_health_registry import ServiceHealthRegistry


# ── Process requirements ──────────────────────────────────────────────────────

_GLUE_PROCESS_REQUIREMENTS  = ProcessRequirements.requires("robot")
_CLEAN_PROCESS_REQUIREMENTS = ProcessRequirements.requires("robot")


def _build_health_registry(robot_app) -> ServiceHealthRegistry:
    """
    Builds a ServiceHealthRegistry that performs real operational health checks.
    Services implementing IHealthCheckable are auto-registered via register_service().
    Services without health semantics (vision stub) are registered with a lambda.
    """
    registry = ServiceHealthRegistry()

    robot = robot_app.get_optional_service("robot")
    if robot is not None:
        registry.register_service("robot", robot)

    weight = robot_app.get_optional_service("weight")
    if weight is not None:
        registry.register_service("weight", weight)

    vision = robot_app.get_optional_service("vision")
    if vision is not None:
        # VisionService has no health semantics yet — registered as always available
        # Replace this with registry.register_service("vision", vision)
        # once VisionService implements IHealthCheckable
        registry.register("vision", lambda: True)

    return registry


def _build_dashboard_plugin(robot_app):
    from src.plugins.base.widget_plugin import WidgetPlugin
    from src.robot_systems.glue.dashboard.glue_dashboard import GlueDashboard

    robot_service   = robot_app.get_service("robot")
    health_registry = _build_health_registry(robot_app)

    return WidgetPlugin(
        widget_factory=lambda ms: GlueDashboard.create(
            robot_service     = robot_service,
            settings_service  = robot_app._settings_service,
            messaging_service = ms,
            weight_service    = robot_app.get_optional_service("weight"),
            app_manager       = robot_app.application_manager,
            service_checker   = health_registry.check,
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
    from src.robot_systems.glue.glue_settings import GlueSettingsFactory, GlueSettingsPluginService

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
