from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.hardware.vacuum_pump.interfaces.i_vacuum_pump_transport import IVacuumPumpTransport


class ModbusVacuumPumpTransport(ModbusRegisterTransport, IVacuumPumpTransport):
    """Modbus RTU transport for vacuum pump control boards."""

