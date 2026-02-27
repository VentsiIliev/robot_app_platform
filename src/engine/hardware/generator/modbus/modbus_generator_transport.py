from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.hardware.generator.interfaces.i_generator_transport import IGeneratorTransport


class ModbusGeneratorTransport(ModbusRegisterTransport, IGeneratorTransport):
    """Modbus RTU transport for generator relay boards."""
