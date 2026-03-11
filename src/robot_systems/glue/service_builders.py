# src/robot_systems/glue/service_builders.py
from src.robot_systems.glue.service_ids import ServiceID
from src.robot_systems.glue.settings_ids import SettingsID
from src.robot_systems.glue.service_ids import ServiceID
from src.robot_systems.glue.settings_ids import SettingsID


# ── Private adapter ───────────────────────────────────────────────────────────
class _LiveConfigTransport:
    """
    IRegisterTransport adapter that reads ModbusConfig fresh from the settings
    cache on every operation.

    Solves the stale-port problem: ModbusRegisterTransport snapshots port/baud
    at construction time.  This wrapper creates a fresh transport per call using
    whatever the settings service currently holds — so a user can change the
    Modbus config in the UI, save, and the next laser operation picks it up
    immediately without restarting.
    """

    def __init__(self, get_config):
        self._get_config = get_config

    def _fresh(self):
        from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
        cfg = self._get_config()
        return ModbusRegisterTransport(
            port=cfg.port,
            slave_address=cfg.slave_address,
            baudrate=cfg.baudrate,
            bytesize=cfg.bytesize,
            stopbits=cfg.stopbits,
            parity=cfg.parity,
            timeout=cfg.timeout,
        )

    def write_register(self, address: int, value: int) -> None:
        self._fresh().write_register(address, value)

    def read_register(self, address: int) -> int:
        return self._fresh().read_register(address)

    def write_registers(self, address: int, values: list) -> None:
        self._fresh().write_registers(address, values)

    def read_registers(self, address: int, count: int) -> list:
        return self._fresh().read_registers(address, count)



def _build_calibration_service(robot_system):
    from src.engine.robot.calibration.robot_calibration_service import RobotCalibrationService
    from src.engine.robot.calibration.robot_calibration.config_helpers import (
        RobotCalibrationConfig, RobotCalibrationEventsConfig,
    )
    from src.shared_contracts.events.robot_events import RobotCalibrationTopics
    from src.robot_systems.glue.navigation import GlueNavigationService

    calib_settings = robot_system._robot_calibration
    robot_settings = robot_system._robot_config
    nav_service    = GlueNavigationService(robot_system.get_service(ServiceID.NAVIGATION))

    events_config = RobotCalibrationEventsConfig(
        broker=robot_system._messaging_service,
        calibration_start_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_START,
        calibration_stop_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_STOP,
        calibration_image_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_IMAGE,
        calibration_log_topic=RobotCalibrationTopics.ROBOT_CALIBRATION_LOG,
    )

    config = RobotCalibrationConfig(
        vision_service=robot_system._vision,
        robot_service=robot_system._robot,
        navigation_service=nav_service,
        height_measuring_service=robot_system._height_measuring_service,
        required_ids=calib_settings.required_ids,
        z_target=calib_settings.z_target,
        robot_tool=robot_settings.robot_tool,
        robot_user=robot_settings.robot_user,
        velocity=calib_settings.velocity,
        acceleration=calib_settings.acceleration,
        axis_mapping_config=calib_settings.axis_mapping,
    )

    return RobotCalibrationService(
        config=config,
        adaptive_config=calib_settings.adaptive_movement,
        events_config=events_config,
    )

def _build_height_measuring_services(robot_system):
    from src.engine.robot.height_measuring.laser_detector import LaserDetector
    from src.engine.robot.height_measuring.laser_detection_service import LaserDetectionService
    from src.engine.robot.height_measuring.laser_calibration_service import LaserCalibrationService
    from src.engine.robot.height_measuring.height_measuring_service import HeightMeasuringService
    from src.robot_systems.glue.tools.glue_laser_control import GlueLaserControl

    settings     = robot_system.get_settings(SettingsID.HEIGHT_MEASURING_SETTINGS)
    robot_config = robot_system.get_settings(SettingsID.ROBOT_CONFIG)
    calib_repo   = robot_system._settings_service.get_repo(SettingsID.HEIGHT_MEASURING_CALIBRATION)

    # Read modbus config fresh from settings on every operation — not at build time.
    # This means updating modbus settings in the UI takes effect immediately on
    # the next laser operation without requiring a restart.
    def _get_modbus_config():
        return robot_system.get_settings(SettingsID.MODBUS_CONFIG)

    transport = _LiveConfigTransport(_get_modbus_config)

    laser_control = GlueLaserControl(transport)
    detector      = LaserDetector(settings.detection)
    detection_svc = LaserDetectionService(
        detector=detector,
        laser=laser_control,
        vision_service=robot_system._vision,
        config=settings.detection,
        exposure_control=robot_system._vision
    )
    calibration_svc = LaserCalibrationService(
        laser_service=detection_svc,
        robot_service=robot_system._robot,
        repository=calib_repo,
        config=settings.calibration,
        tool=robot_config.robot_tool,
        user=robot_config.robot_user,
    )
    measuring_svc = HeightMeasuringService(
        laser_service=detection_svc,
        robot_service=robot_system._robot,
        repository=calib_repo,
        config=settings.measuring,
        tool=robot_config.robot_tool,
        user=robot_config.robot_user,
        depth_map_repository=robot_system._settings_service.get_repo(SettingsID.DEPTH_MAP_DATA),
    )
    return measuring_svc, calibration_svc, detection_svc

def build_weight_cell_service(ctx):
    from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
    cells_config = ctx.settings.get(SettingsID.GLUE_CELLS)
    return build_http_weight_cell_service(cells_config=cells_config, messaging=ctx.messaging_service)


def build_motor_service(ctx):
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
            motor_addresses               = [0, 2, 4, 6],
            address_to_error_prefix       = {0: 1, 2: 2, 4: 3, 6: 4},
        ),
        error_decoder = GlueMotorErrorDecoder(),
    )


def build_vision_service(ctx):
    import os
    from src.engine.vision.vision_service import VisionService
    from src.engine.vision.implementation.VisionSystem.VisionSystem import VisionSystem
    from src.engine.vision.implementation.VisionSystem.core.service.internal_service import Service

    ctx.settings.get(SettingsID.VISION_CAMERA_SETTINGS)
    settings_file_path = ctx.settings.get_repo(SettingsID.VISION_CAMERA_SETTINGS).file_path

    system_dir       = os.path.dirname(os.path.abspath(__file__))
    calibration_path = os.path.join(system_dir, "storage", "settings", "vision", "data")
    os.makedirs(calibration_path, exist_ok=True)

    service = Service(data_storage_path=calibration_path, settings_file_path=settings_file_path)
    vision_system = VisionSystem(
        storage_path      = calibration_path,
        messaging_service = ctx.messaging_service,
        service           = service,
    )
    return VisionService(vision_system)


def build_tool_service(ctx):
    from src.engine.robot.tool_changer import ToolChanger
    from src.engine.robot.tool_manager import ToolManager

    tc_settings  = ctx.settings.get(SettingsID.TOOL_CHANGER_CONFIG)
    tool_changer = ToolChanger(slots=tc_settings.slots, tools=tc_settings.tools)
    robot_config = ctx.settings.get(SettingsID.ROBOT_CONFIG)

    return ToolManager(
        motion_service = ctx.motion,
        tool_changer   = tool_changer,
        robot_config   = robot_config,
    )

