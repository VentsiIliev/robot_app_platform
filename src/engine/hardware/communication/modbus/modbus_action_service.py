import logging
import os
import subprocess
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
                except Exception as exc:
                    self._logger.debug(
                        "Port %s skipped — open failed: %s",
                        info.device,
                        exc,
                    )

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

    def grant_serial_port_permissions(self) -> List[str]:
        targets = self._serial_permission_targets()
        if not targets:
            self._logger.info("No USB serial ports found for permission update")
            return []

        command = ["chmod", "a+rw", *targets]
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            command.insert(0, "pkexec")

        try:
            self._logger.info("Granting serial port permissions for: %s", targets)
            subprocess.run(command, check=True, timeout=60)
            return targets
        except Exception as exc:
            self._logger.warning("Failed to grant serial port permissions: %s", exc)
            return []

    def _serial_permission_targets(self) -> List[str]:
        if os.name != "posix":
            return []

        try:
            import serial.tools.list_ports

            targets: List[str] = []
            for info in serial.tools.list_ports.comports():
                device = str(getattr(info, "device", ""))
                if getattr(info, "vid", None) is None:
                    continue
                if device.startswith(("/dev/ttyUSB", "/dev/ttyACM")):
                    targets.append(device)
            return sorted(set(targets))
        except Exception:
            self._logger.exception("Failed to list USB serial ports for permission update")
            return []
