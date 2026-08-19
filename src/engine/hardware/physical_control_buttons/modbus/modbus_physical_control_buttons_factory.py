from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
from src.engine.hardware.peripherals import PeripheralConfig
from src.engine.hardware.physical_control_buttons.interfaces.i_physical_control_buttons import IPhysicalControlButtons
from src.engine.hardware.physical_control_buttons.modbus.modbus_physical_control_buttons import ModbusPhysicalControlButtons


def build_modbus_physical_control_buttons(
    modbus_config: ModbusConfig,
    peripheral_config: PeripheralConfig,
) -> IPhysicalControlButtons | None:
    binding = peripheral_config.get("physical_control_buttons")
    if binding is None or not binding.inputs:
        return None
    slave_name = modbus_config.find_slave_name(binding.slave_id)
    transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, slave_name)
    return ModbusPhysicalControlButtons(transport, binding.inputs, binding.outputs)
