from src.robot_systems.glue.service_ids import ServiceID
from src.robot_systems.glue.settings_ids import SettingsID

def _build_workpiece_editor_application(robot_system):
    import os, inspect
    from contour_editor import SettingsConfig, SettingsGroup
    from src.applications.base.widget_application import WidgetApplication
    from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory
    from src.robot_systems.glue.workpieces.repository.json_workpiece_repository import JsonWorkpieceRepository
    from src.robot_systems.glue.workpieces.service.workpiece_service import WorkpieceService
    from src.robot_systems.glue.applications.workpiece_editor.service.workpiece_editor_service import WorkpieceEditorService
    from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
    from src.robot_systems.glue.settings.glue import GlueSettingKey
    from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.segment_settings_provider import \
        SegmentSettingsProvider
    from src.robot_systems.glue.applications.workpiece_editor.workpiece_editor.config.segment_editor_config import \
        SegmentEditorConfig
    from src.robot_systems.glue.settings.glue_workpiece_form_schema import build_glue_workpiece_form_schema

    system_dir   = os.path.dirname(inspect.getfile(GlueRobotSystem))
    storage_root = os.path.join(system_dir, "storage", "workpieces")

    catalog    = robot_system._settings_service.get(SettingsID.GLUE_CATALOG)
    glue_types = catalog.get_all_names() if hasattr(catalog, "get_all_names") else []

    form_schema = build_glue_workpiece_form_schema(glue_types)

    # per-segment settings panel — glue-specific, built here so editor knows nothing about it
    provider = SegmentSettingsProvider(material_types=glue_types)
    defaults = provider.get_default_values()
    settings_config = SettingsConfig(
        default_settings=defaults,
        groups=[
            SettingsGroup("General", [
                GlueSettingKey.SPRAY_WIDTH.value,
                GlueSettingKey.SPRAYING_HEIGHT.value,
                GlueSettingKey.GLUE_TYPE.value,
            ]),
            SettingsGroup("Forward Motion", [
                GlueSettingKey.FORWARD_RAMP_STEPS.value,
                GlueSettingKey.INITIAL_RAMP_SPEED.value,
                GlueSettingKey.INITIAL_RAMP_SPEED_DURATION.value,
                GlueSettingKey.MOTOR_SPEED.value,
            ]),
            SettingsGroup("Reverse Motion", [
                GlueSettingKey.REVERSE_DURATION.value,
                GlueSettingKey.SPEED_REVERSE.value,
                GlueSettingKey.REVERSE_RAMP_STEPS.value,
            ]),
            SettingsGroup("Robot", [
                "velocity", "acceleration",
                GlueSettingKey.RZ_ANGLE.value,
                "adaptive_spacing_mm",
                "spline_density_multiplier",
                "smoothing_lambda",
            ]),
            SettingsGroup("Generator", [
                GlueSettingKey.TIME_BETWEEN_GENERATOR_AND_GLUE.value,
                GlueSettingKey.GENERATOR_TIMEOUT.value,
            ]),
            SettingsGroup("Thresholds (mm)", [
                GlueSettingKey.REACH_START_THRESHOLD.value,
                GlueSettingKey.REACH_END_THRESHOLD.value,
            ]),
            SettingsGroup("Pump Speed", [
                "glue_speed_coefficient",
                "glue_acceleration_coefficient",
            ]),
        ],
        combo_field_key=GlueSettingKey.GLUE_TYPE.value,
    )
    segment_config = SegmentEditorConfig(
        settings_config   = settings_config,
        settings_provider = provider,
    )

    repo              = JsonWorkpieceRepository(storage_root)
    workpiece_service = WorkpieceService(repo)

    service = WorkpieceEditorService(
        vision_service    = robot_system.get_optional_service(ServiceID.VISION),
        workpiece_service = workpiece_service,
        form_schema       = form_schema,
        segment_config    = segment_config,
    )
    return WidgetApplication(
        widget_factory=lambda ms: WorkpieceEditorFactory(ms).build(service)
    )

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
    from src.robot_systems.glue.applications.dashboard.glue_dashboard import GlueDashboard

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

def _build_user_management_application(robot_system):
    import os, inspect
    from src.applications.base.widget_application import WidgetApplication
    from src.applications.user_management.user_management_factory import UserManagementFactory
    from src.applications.user_management.service.user_management_application_service import UserManagementApplicationService
    from src.applications.user_management.domain.csv_user_repository import CsvUserRepository
    from src.robot_systems.glue.glue_robot_system import GlueRobotSystem
    from src.robot_systems.glue.settings.glue_user_schema import GLUE_USER_SCHEMA

    storage = os.path.join(
        os.path.dirname(inspect.getfile(GlueRobotSystem)),
        "storage", "users", "users.csv",
    )
    service = UserManagementApplicationService(CsvUserRepository(storage, GLUE_USER_SCHEMA))
    return WidgetApplication(widget_factory=lambda _ms: UserManagementFactory().build(service))


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
    from src.robot_systems.glue.applications.glue_settings import GlueSettingsFactory, GlueSettingsApplicationService

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
