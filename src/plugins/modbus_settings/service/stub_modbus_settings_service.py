from typing import List

from src.engine.hardware.modbus import ModbusConfig
from src.plugins.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class StubModbusSettingsService(IModbusSettingsService):

    def __init__(self):
        self._config = ModbusConfig()

    def load_config(self) -> ModbusConfig:
        print("[StubModbusSettingsService] load_config")
        return self._config

    def save_config(self, config: ModbusConfig) -> None:
        self._config = config
        print(f"[StubModbusSettingsService] save_config → {config}")

    def detect_ports(self) -> List[str]:
        print("[StubModbusSettingsService] detect_ports")
        return ["COM1", "COM3", "COM5", "/dev/ttyUSB0", "/dev/ttyUSB1"]

    def test_connection(self, config: ModbusConfig) -> bool:
        print(f"[StubModbusSettingsService] test_connection → port={config.port}")
        return True
