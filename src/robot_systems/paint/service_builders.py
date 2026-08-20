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
            peripheral_config.peripherals.get("vacuum_pump")
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
                on_value=binding.commands.get("on", 1) if binding is not None else 1,
                off_value=binding.commands.get("off", 0) if binding is not None else 0,
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


def build_dryer_service(ctx):
    from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
    from src.engine.hardware.dryer.dryer_controller import DryerController
    from src.engine.hardware.dryer.dryer_service import DryerService
    from src.engine.hardware.dryer.models.dryer_config import DryerConfig
    from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerRegisterMap

    try:
        modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
        peripheral_config = ctx.settings.get(SettingsID.PERIPHERALS)
        dryer_config = ctx.settings.get(SettingsID.DRYER_CONFIG)
        if not isinstance(modbus_config, ModbusConfig):
            return None
        if not isinstance(peripheral_config, PeripheralConfig):
            return None
        if not isinstance(dryer_config, DryerConfig):
            return None
        binding = peripheral_config.peripherals.get("dryer")
        if binding is None:
            return None
        slave_name = modbus_config.find_slave_name(binding.slave_id)
        register_map = DryerRegisterMap.from_mapping({**binding.inputs, **binding.outputs})

        def build_controller(config):
            transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
            return DryerController(transport, config, register_map)

        service = DryerService(build_controller, dryer_config)
        if binding.enabled and not service.enable():
            from src.engine.hardware.peripherals import PeripheralBinding

            disabled = PeripheralBinding(
                slave_id=binding.slave_id,
                enabled=False,
                inputs=binding.inputs,
                outputs=binding.outputs,
                commands=binding.commands,
            )
            ctx.settings.save(
                SettingsID.PERIPHERALS,
                PeripheralConfig({**peripheral_config.peripherals, "dryer": disabled}),
            )
            _logger.error("Dryer disabled after initialization failure: %s", service.last_error)
        return service
    except Exception:
        _logger.exception("Dryer service could not be built; continuing without it")
        return None


def build_vacuum_sensor_service(ctx):
    """Build the configured vacuum sensor using the selected slave transport."""
    from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
    from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
    from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService

    try:
        modbus_config = ctx.settings.get(CommonSettingsID.MODBUS_CONFIG)
        peripheral_config = ctx.settings.get(SettingsID.PERIPHERALS)
        if not isinstance(modbus_config, ModbusConfig) or not isinstance(peripheral_config, PeripheralConfig):
            return None
        binding = peripheral_config.peripherals.get("vacuum_sensor")
        if binding is None:
            return None
        sensor_register = binding.inputs.get("sensor") or binding.outputs.get("sensor")
        if sensor_register is None:
            return None
        slave_name = modbus_config.find_slave_name(binding.slave_id)
        transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
        return VacuumSensorService(
            transport=transport,
            config=VacuumSensorConfig(sensor_register=sensor_register, detected_value=0),
        )
    except Exception:
        _logger.exception("Vacuum sensor service could not be built; continuing without it")
        return None
