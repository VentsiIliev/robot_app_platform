import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.plugins.base.plugin_interface import IPlugin
from src.plugins.modbus_settings.modbus_settings_factory import ModbusSettingsFactory
from src.plugins.modbus_settings.service.modbus_settings_plugin_service import ModbusSettingsPluginService


class ModbusSettingsPlugin(IPlugin):

    def __init__(self, settings_service=None):
        self._logger  = logging.getLogger(self.__class__.__name__)
        self._service = ModbusSettingsPluginService(settings_service)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("ModbusSettingsPlugin registered")

    def create_widget(self) -> AppWidget:
        return ModbusSettingsFactory().build(self._service)