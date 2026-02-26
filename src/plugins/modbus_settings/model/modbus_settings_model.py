import logging
from typing import List, Optional

from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.modbus_settings.model.mapper import ModbusSettingsMapper
from src.plugins.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class ModbusSettingsModel(IPluginModel):

    def __init__(self, settings_service: IModbusSettingsService, action_service: IModbusActionService):
        self._settings = settings_service
        self._actions  = action_service
        self._config: Optional[ModbusConfig] = None
        self._logger   = logging.getLogger(self.__class__.__name__)

    def load(self) -> ModbusConfig:
        self._config = self._settings.load_config()
        self._logger.debug("Modbus config loaded")
        return self._config

    def save(self, flat: dict, **kwargs) -> None:
        base    = self._config if self._config is not None else ModbusConfig()
        updated = ModbusSettingsMapper.from_flat_dict(flat, base)
        self._settings.save_config(updated)
        self._config = updated
        self._logger.info("Modbus config saved")

    def detect_ports(self) -> List[str]:
        return self._actions.detect_ports()

    def test_connection(self, config: ModbusConfig) -> bool:
        return self._actions.test_connection(config)

    def config_from_flat(self, flat: dict) -> ModbusConfig:
        base = self._config if self._config is not None else ModbusConfig()
        return ModbusSettingsMapper.from_flat_dict(flat, base)
