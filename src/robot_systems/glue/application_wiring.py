from src.robot_systems.glue.service_ids import ServiceID

from src.robot_systems.glue.settings_ids import SettingsID


def _build_dashboard_application(system):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.dashboard.glue_dashboard import GlueDashboard

    coordinator = system.coordinator
    settings_service = system._settings_service
    weight_service = system.get_optional_service(ServiceID.WEIGHT)

    return WidgetApplication(
        widget_factory=lambda ms: GlueDashboard.create(
            coordinator=coordinator,
            settings_service=settings_service,
            messaging_service=ms,
            weight_service=weight_service,
        )
    )


def _build_glue_cell_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.glue_cell_settings import GlueCellSettingsFactory, GlueCellSettingsService

    service = GlueCellSettingsService(
        robot_app._settings_service,
        settings_key=SettingsID.GLUE_CELLS,
        weight_service=robot_app.get_service(ServiceID.WEIGHT)
    )
    return WidgetApplication(
        widget_factory=lambda ms: GlueCellSettingsFactory().build(service, ms)
    )


def _build_robot_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
    from src.applications.robot_settings.service.robot_settings_application_service import \
        RobotSettingsApplicationService

    service = RobotSettingsApplicationService(
        robot_app._settings_service,
        config_key=SettingsID.ROBOT_CONFIG,
        calibration_key=SettingsID.ROBOT_CALIBRATION,
    )
    return WidgetApplication(widget_factory=lambda _ms: RobotSettingsFactory().build(service))


def _build_glue_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.glue_settings import GlueSettingsFactory, GlueSettingsApplicationService

    service = GlueSettingsApplicationService(robot_app._settings_service)
    return WidgetApplication(widget_factory=lambda _ms: GlueSettingsFactory().build(service))


def _build_modbus_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.engine.hardware.communication.modbus.modbus_action_service import ModbusActionService
    from src.applications.modbus_settings import ModbusSettingsFactory, ModbusSettingsApplicationService

    settings_service = ModbusSettingsApplicationService(
        robot_app._settings_service,
        config_key=SettingsID.MODBUS_CONFIG,
    )

    action_service = ModbusActionService()
    return WidgetApplication(
        widget_factory=lambda _ms: ModbusSettingsFactory().build(settings_service, action_service)
    )
