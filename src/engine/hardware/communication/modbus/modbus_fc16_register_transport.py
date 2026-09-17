from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus_register_transport import (
    ModbusRegisterTransport,
)


class ModbusFc16RegisterTransport(ModbusRegisterTransport):
    """Standard Modbus RTU registers with FC16 for single-register writes."""

    def write_register(self, address: int, value: int) -> None:
        self.write_registers(address, [value])
