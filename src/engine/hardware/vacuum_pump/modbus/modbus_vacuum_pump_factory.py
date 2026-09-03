from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_controller import IVacuumPumpController
from src.engine.hardware.vacuum_pump.models.vacuum_pump_config import VacuumPumpConfig
from src.engine.hardware.vacuum_pump.vacuum_pump_controller import VacuumPumpController


def build_modbus_vacuum_pump_controller(
    modbus_config: ModbusConfig,
    vacuum_config: VacuumPumpConfig | None = None,
    profile_name: str = "default",
) -> IVacuumPumpController:
    from src.engine.hardware.communication.transport_registry import DEFAULT_TRANSPORT_REGISTRY
    if hasattr(modbus_config, "get_slave"):
        transport = DEFAULT_TRANSPORT_REGISTRY.build_for_slave(modbus_config, profile_name)
    else:
        from src.engine.hardware.vacuum_pump.modbus.modbus_vacuum_pump_transport import (
            ModbusVacuumPumpTransport,
        )
        transport = ModbusVacuumPumpTransport(
            port=modbus_config.port,
            slave_address=modbus_config.slave_address,
            baudrate=modbus_config.baudrate,
            bytesize=modbus_config.bytesize,
            stopbits=modbus_config.stopbits,
            parity=modbus_config.parity,
            timeout=modbus_config.timeout,
        )
    return VacuumPumpController(
        transport=transport,
        config=vacuum_config or VacuumPumpConfig(),
    )
