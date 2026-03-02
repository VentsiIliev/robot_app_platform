from src.robot_systems.glue.service_ids import ServiceID

from src.robot_systems.glue.settings_ids import SettingsID

def _build_camera_settings_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.camera_settings.camera_settings_factory import CameraSettingsFactory
    from src.applications.camera_settings.service.camera_settings_application_service import CameraSettingsApplicationService
    from src.robot_systems.glue.service_ids import ServiceID

    service = CameraSettingsApplicationService(
        settings_service = robot_system._settings_service,
        vision_service   = robot_system.get_optional_service(ServiceID.VISION),
    )
    factory = CameraSettingsFactory()
    return WidgetApplication(
        widget_factory=lambda ms: factory.build(service, ms)
    )

def _build_calibration_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.calibration.calibration_factory import CalibrationFactory
    from src.applications.calibration.service.calibration_application_service import CalibrationApplicationService

    service = CalibrationApplicationService(
        vision_service=robot_system.get_optional_service(ServiceID.VISION),
    )
    return WidgetApplication(
        widget_factory=lambda ms: CalibrationFactory(ms).build(service)
    )


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

def _build_broker_debug_application(robot_system):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.broker_debug.broker_debug_factory import BrokerDebugFactory
    from src.applications.broker_debug.service.broker_debug_application_service import BrokerDebugApplicationService

    return WidgetApplication(
        widget_factory=lambda ms: BrokerDebugFactory(ms).build(
            BrokerDebugApplicationService(ms)
        )
    )


def _build_glue_cell_settings_application(robot_app):
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.glue_cell_settings import GlueCellSettingsFactory, GlueCellSettingsService

    service = GlueCellSettingsService(
        robot_app._settings_service,
        settings_key=SettingsID.GLUE_CELLS,
        weight_service=robot_app.get_optional_service(ServiceID.WEIGHT)
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
