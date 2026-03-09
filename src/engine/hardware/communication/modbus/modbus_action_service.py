import logging
from typing import List

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig


class ModbusActionService(IModbusActionService):

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)

    def detect_ports(self) -> List[str]:
        try:
            import serial.tools.list_ports
            import serial

            active: List[str] = []
            for info in serial.tools.list_ports.comports():
                # vid is an integer assigned by the OS to every USB device.
                # Built-in UART ports (ttyS*, COM1-4) always have vid=None.
                # RS485 adapters always connect via USB — so vid=None means skip.
                if info.vid is None:
                    continue

                # Probe: try to open the port to confirm it is physically
                # accessible right now. Drops disconnected dongles and ports
                # with I/O errors (termios ENXIO, permission denied, in-use).
                try:
                    with serial.Serial(port=info.device, baudrate=9600, timeout=0.05):
                        pass
                    active.append(info.device)
                except serial.SerialException:
                    self._logger.debug("Port %s skipped — open failed", info.device)

            self._logger.info("RS485 ports detected: %s", active)
            return active

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
