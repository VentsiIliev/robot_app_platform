# src/robot_systems/glue/service_builders.y_pixels
from src.engine.common_settings_ids import CommonSettingsID
from src.robot_systems.glue.settings_ids import SettingsID

def _build_generator_service(robot_system):
    from src.engine.hardware.generator.modbus.modbus_generator_factory import build_modbus_generator_controller
    try:
        modbus_config = robot_system.get_settings(CommonSettingsID.MODBUS_CONFIG)
        return build_modbus_generator_controller(modbus_config)
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Generator service could not be built — continuing without it")
        return None


def build_weight_cell_service(ctx):
    from src.engine.hardware.weight.http.http_weight_cell_factory import build_http_weight_cell_service
    cells_config = ctx.settings.get(SettingsID.GLUE_CELLS)
    return build_http_weight_cell_service(cells_config=cells_config, messaging=ctx.messaging_service)


def build_motor_service(ctx):
    from src.engine.hardware.motor.modbus.modbus_motor_factory import build_modbus_motor_service
    from src.engine.hardware.motor.models.motor_config import MotorConfig
    from src.robot_systems.glue.motor.glue_motor_error_decoder import GlueMotorErrorDecoder
    modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
    topology      = ctx.settings.get(SettingsID.GLUE_MOTOR_CONFIG)
    return build_modbus_motor_service(
        modbus_config = modbus_config,
        motor_config  = MotorConfig(
            health_check_trigger_register = topology.health_check_trigger_register,
            motor_error_count_register    = topology.motor_error_count_register,
            motor_error_registers_start   = topology.motor_error_registers_start,
            motor_addresses               = topology.get_addresses(),
            address_to_error_prefix       = topology.get_address_to_error_prefix(),
            health_check_delay_s          = topology.health_check_delay_s,
        ),
        error_decoder = GlueMotorErrorDecoder(),
    )

from src.robot_systems.glue.processes.glue_dispensing.i_glue_type_resolver import IGlueTypeResolver


class GlueCellTypeResolver(IGlueTypeResolver):
    """Maps glue_type string → motor_address int from the live GlueCellsConfig."""

    def __init__(self, glue_cells_config) -> None:
        self._config = glue_cells_config

    def resolve(self, glue_type: str) -> int:
        try:
            for cell in getattr(self._config, "cells", []):
                cell_type = (
                    getattr(cell, "glue_type", None)
                    or getattr(cell, "glueType", None)
                    or getattr(cell, "type", None)
                )
                addr = self._first_present_attr(cell, "motor_address", "motorAddress")
                if cell_type == glue_type and addr is not None:
                    return int(addr)
        except Exception:
            pass
        return -1

    def _first_present_attr(self, obj, *names):
        for name in names:
            value = getattr(obj, name, None)
            if value is not None:
                return value
        return None
