import logging
from typing import List

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig


class ModbusActionService(IModbusActionService):

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def detect_ports(self) -> List[str]:
        try:
            self._logger.info("Detecting serial ports")
            import serial.tools.list_ports
            return [p.device for p in serial.tools.list_ports.comports()]
        except Exception:
            self._logger.exception("Failed to detect serial ports")
            return []

    def test_connection(self, config: ModbusConfig) -> bool:
        try:
            self._logger.info("Testing connection on port '%s'", config.port)
            import serial
            with serial.Serial(
                port=config.port,
                baudrate=config.baudrate,
                bytesize=config.bytesize,
                stopbits=config.stopbits,
                parity=config.parity,
                timeout=config.timeout,
            ):
                return True
        except Exception:
            self._logger.warning("Test connection failed for port '%s'", config.port)
            return False