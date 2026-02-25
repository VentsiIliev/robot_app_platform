# Moved to engine layer. This shim exists for backwards compatibility.
from src.engine.hardware.modbus import ModbusConfig, ModbusConfigSerializer

__all__ = ["ModbusConfig", "ModbusConfigSerializer"]