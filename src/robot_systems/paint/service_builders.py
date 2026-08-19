from __future__ import annotations

import logging

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.peripherals import PeripheralConfig
from src.robot_systems.paint.component_ids import SettingsID

_logger = logging.getLogger(__name__)


def build_vacuum_pump_service(ctx):
    from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
    from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_factory import (
        build_modbus_vacuum_pump_controller,
    )

    try:
        modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
        peripheral_config = None
        if isinstance(modbus_config, ModbusConfig):
            peripheral_config = ctx.settings.get(SettingsID.PERIPHERALS)
        binding = (
            peripheral_config.get("vacuum_pump")
            if isinstance(peripheral_config, PeripheralConfig)
            else None
        )
        slave_name = "xinje_ma"
        pump_register = "Y2"
        blow_off_register = "Y3"
        if binding is not None:
            slave_name = modbus_config.find_slave_name(binding.slave_id)
            pump_register = binding.outputs.get("pump", pump_register)
            blow_off_register = binding.outputs.get("blow_off", blow_off_register)
        return build_modbus_vacuum_pump_controller(
            modbus_config=modbus_config,
            profile_name=slave_name,
            vacuum_config=VacuumPumpConfig(
                pump_register=pump_register,
                blow_off_register=blow_off_register,
                blow_off_pulse_seconds=0.2,
            ),
        )
    except Exception:
        _logger.exception("Vacuum pump service could not be built; continuing without it")
        return None


def build_fan_service(ctx):
    from src.engine.hardware.fan.modbus.modbus_fan_factory import build_modbus_fan_control

    try:
        modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
        peripheral_config = ctx.settings.get(SettingsID.PERIPHERALS)
        if not isinstance(modbus_config, ModbusConfig):
            return None
        if not isinstance(peripheral_config, PeripheralConfig):
            return None
        return build_modbus_fan_control(modbus_config, peripheral_config)
    except Exception:
        _logger.exception("Fan service could not be built; continuing without it")
        return None


def build_physical_control_buttons_service(ctx):
    from src.engine.hardware.physical_control_buttons.modbus.modbus_physical_control_buttons_factory import (
        build_modbus_physical_control_buttons,
    )

    try:
        modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
        peripheral_config = ctx.settings.get(SettingsID.PERIPHERALS)
        if not isinstance(modbus_config, ModbusConfig) or not isinstance(peripheral_config, PeripheralConfig):
            return None
        return build_modbus_physical_control_buttons(modbus_config, peripheral_config)
    except Exception:
        _logger.exception("Physical control buttons could not be built; continuing without them")
        return None
