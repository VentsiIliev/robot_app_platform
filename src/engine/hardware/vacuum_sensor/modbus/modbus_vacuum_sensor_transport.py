from __future__ import annotations

from src.engine.hardware.communication.modbus.modbus_register_transport import ModbusRegisterTransport
from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_transport import IVacuumSensorTransport


class ModbusVacuumSensorTransport(ModbusRegisterTransport, IVacuumSensorTransport):
    """Modbus RTU transport for vacuum-sensor relay/coil boards.

    Reads the sensor output as a coil (function code 1), mirroring the
    vacuum-pump transport used on the same relay-board family. Override
    read_register if the sensor is exposed on a discrete input (FC2) or
    a holding register (default FC3) instead.
    """

    def read_register(self, address: int) -> int:
        with self._session() as inst:
            self._logger.debug("Reading sensor coil %s", address)
            return int(inst.read_bit(address, functioncode=1))
