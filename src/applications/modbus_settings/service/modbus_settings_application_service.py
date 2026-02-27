import logging

from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.applications.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class ModbusSettingsApplicationService(IModbusSettingsService):

    def __init__(self, settings_service: ISettingsService, config_key: str):
        self._settings   = settings_service
        self._config_key = config_key
        self._logger     = logging.getLogger(self.__class__.__name__)

    def load_config(self) -> ModbusConfig:
        return self._settings.get(self._config_key)

    def save_config(self, config: ModbusConfig) -> None:
        self._settings.save(self._config_key, config)

