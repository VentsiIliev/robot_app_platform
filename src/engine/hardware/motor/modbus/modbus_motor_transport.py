from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.hardware.motor.interfaces.i_motor_transport import IMotorTransport


class ModbusMotorTransport(ModbusRegisterTransport, IMotorTransport):
    """Modbus RTU transport for motor controller boards."""
