import logging
from typing import List

from src.engine.hardware.modbus import ModbusConfig
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.plugins.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class ModbusSettingsPluginService(IModbusSettingsService):

    def __init__(self, settings_service: ISettingsService):
        self._settings = settings_service
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load_config(self) -> ModbusConfig:
        return self._settings.get("modbus_config")

    def save_config(self, config: ModbusConfig) -> None:
        self._settings.save("modbus_config", config)

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
            self._logger.info("Testing connection to port '%s'", config.port)
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
