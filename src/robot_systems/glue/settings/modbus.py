# Moved to engine layer. This shim exists for backwards compatibility.
from src.engine.hardware.communication.modbus.modbus import ModbusConfig, ModbusConfigSerializer

__all__ = ["ModbusConfig", "ModbusConfigSerializer"]