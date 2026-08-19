from __future__ import annotations

from src.engine.hardware.communication.modbus.xinje_ma_8x8yr_transport import (
    ModbusExceptionResponse,
    XinjeMA8X8YRTransport,
    _crc16,
)
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import (
    IVacuumPumpTransport,
)


class ModbusVacuumPumpTransport(XinjeMA8X8YRTransport, IVacuumPumpTransport):
    """Backward-compatible vacuum-pump view of the Xinje MA transport.

    The protocol implementation belongs to the shared communication layer;
    this name remains for existing vacuum-pump callers and integrations.
    """


__all__ = ["ModbusExceptionResponse", "ModbusVacuumPumpTransport", "_crc16"]
