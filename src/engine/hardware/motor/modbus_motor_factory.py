from __future__ import annotations
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.motor.interfaces.i_motor_controller import IMotorController
from src.engine.hardware.motor.models.motor_config import MotorConfig
from src.engine.hardware.motor.motor_controller import MotorController
from src.engine.hardware.motor.modbus.modbus_motor_transport import ModbusMotorTransport


def build_modbus_motor_controller(
    modbus_config: ModbusConfig,
    motor_config:  MotorConfig = None,
) -> IMotorController:
    """
    Build a MotorController wired to Modbus RTU.
    Uses ModbusConfig.slave_address as the motor board slave ID.
    """
    transport = ModbusMotorTransport(
        port          = modbus_config.port,
        slave_address = modbus_config.slave_address,
        baudrate      = modbus_config.baudrate,
        bytesize      = modbus_config.bytesize,
        stopbits      = modbus_config.stopbits,
        parity        = modbus_config.parity,
        timeout       = modbus_config.timeout,
    )
    return MotorController(transport=transport, config=motor_config or MotorConfig())