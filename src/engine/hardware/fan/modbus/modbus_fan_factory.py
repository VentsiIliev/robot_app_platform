from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.fan.interfaces.i_fan_control import IFanControl
from src.engine.hardware.fan.modbus.modbus_fan_control import ModbusFanControl
from src.engine.hardware.peripherals import PeripheralConfig


def build_modbus_fan_control(
    modbus_config: ModbusConfig,
    peripheral_config: PeripheralConfig,
) -> IFanControl | None:
    # Construct configured hardware even when its runtime enabled flag is off;
    # Device Control needs the controller in order to perform the enable check.
    binding = peripheral_config.peripherals.get("fan")
    if binding is None:
        return None
    slave_name = modbus_config.find_slave_name(binding.slave_id)
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
    return ModbusFanControl(
        transport=transport,
        register=binding.outputs.get("fan", "Y0"),
        on_value=binding.commands.get("on", 1),
        off_value=binding.commands.get("off", 0),
    )
