# src/robot_systems/glue/service_builders.py
from src.robot_systems.glue.settings_ids import SettingsID


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