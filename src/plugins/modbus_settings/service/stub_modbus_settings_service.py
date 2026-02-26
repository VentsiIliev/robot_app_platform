from src.engine.hardware.communication.modbus.modbus import ModbusConfig
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