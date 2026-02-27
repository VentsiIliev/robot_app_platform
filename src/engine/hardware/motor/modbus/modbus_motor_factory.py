from __future__ import annotations
from typing import Optional  # used by error_decoder

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.motor.interfaces.i_motor_service import IMotorService
from src.engine.hardware.motor.interfaces.i_motor_error_decoder import IMotorErrorDecoder
from src.engine.hardware.motor.models.motor_config import MotorConfig
from src.engine.hardware.motor.motor_service import MotorService
from src.engine.hardware.motor.modbus.modbus_motor_transport import ModbusMotorTransport


def build_modbus_motor_service(
    modbus_config:  ModbusConfig,
    motor_config:   MotorConfig,
    error_decoder:  Optional[IMotorErrorDecoder] = None,
) -> IMotorService:
    """
    Build a MotorService wired to Modbus RTU.

    motor_config  — required: register map and motor topology for this board.
                    Instantiate MotorConfig explicitly in the robot system that
                    owns the hardware — no generic defaults exist.
    error_decoder — inject a system-specific IMotorErrorDecoder to translate
                    board firmware error codes into human-readable descriptions.
                    If omitted, raw integer codes are logged with a warning.
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
    return MotorService(
        transport     = transport,
        config        = motor_config,
        error_decoder = error_decoder,
    )
