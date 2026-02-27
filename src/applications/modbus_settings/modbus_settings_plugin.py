import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.hardware.communication.modbus.i_modbus_action_service import IModbusActionService
from src.applications.base.application_interface import IApplication
from src.applications.modbus_settings.modbus_settings_factory import ModbusSettingsFactory
from src.applications.modbus_settings.service.i_modbus_settings_service import IModbusSettingsService


class ModbusSettingsApplication(IApplication):

    def __init__(self, settings_service: IModbusSettingsService, action_service: IModbusActionService):
        self._logger          = logging.getLogger(self.__class__.__name__)
        self._settings_service = settings_service
        self._action_service   = action_service

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("ModbusSettingsApplication registered")

    def create_widget(self) -> AppWidget:
        return ModbusSettingsFactory().build(self._settings_service, self._action_service)
