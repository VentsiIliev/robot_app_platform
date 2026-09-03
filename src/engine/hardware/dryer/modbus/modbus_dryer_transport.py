from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.hardware.dryer.interfaces.i_dryer_transport import IDryerTransport


class ModbusDryerTransport(ModbusRegisterTransport, IDryerTransport):
    """Modbus RTU transport for dryer boards."""
