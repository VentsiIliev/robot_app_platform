from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_service import IVacuumSensorService
from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_transport import IVacuumSensorTransport
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.vacuum_sensor.modbus.modbus_vacuum_sensor_transport import (
    ModbusVacuumSensorTransport,
)
from src.engine.hardware.vacuum_sensor.vacuum_sensor_service import VacuumSensorService


def build_modbus_vacuum_sensor_service(
    modbus_config:  ModbusConfig,
    sensor_config:  VacuumSensorConfig,
) -> IVacuumSensorService:
    """Build a VacuumSensorService wired to Modbus RTU."""
    transport: IVacuumSensorTransport = ModbusVacuumSensorTransport(
        port          = modbus_config.port,
        slave_address = modbus_config.slave_address,
        baudrate      = modbus_config.baudrate,
        bytesize      = modbus_config.bytesize,
        stopbits      = modbus_config.stopbits,
        parity        = modbus_config.parity,
        timeout       = modbus_config.timeout,
    )
    return VacuumSensorService(transport=transport, config=sensor_config)
