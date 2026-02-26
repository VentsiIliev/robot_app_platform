import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.plugins.base.plugin_interface import IPlugin
from src.plugins.modbus_settings.modbus_settings_factory import ModbusSettingsFactory
from src.plugins.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class ModbusSettingsPlugin(IPlugin):

    def __init__(self, settings_service: IModbusSettingsService, action_service: IModbusActionService):
        self._logger          = logging.getLogger(self.__class__.__name__)
        self._settings_service = settings_service
        self._action_service   = action_service

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("ModbusSettingsPlugin registered")

    def create_widget(self) -> AppWidget:
        return ModbusSettingsFactory().build(self._settings_service, self._action_service)
