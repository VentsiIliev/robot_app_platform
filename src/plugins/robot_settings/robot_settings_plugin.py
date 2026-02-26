import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.plugins.base.plugin_interface import IPlugin
from src.plugins.robot_settings.robot_settings_factory import RobotSettingsFactory
from src.plugins.robot_settings.service.robot_settings_plugin_service import RobotSettingsPluginService


class RobotSettingsPlugin(IPlugin):

    def __init__(self, settings_service: ISettingsService):
        self._logger  = logging.getLogger(self.__class__.__name__)
        self._service = RobotSettingsPluginService(settings_service)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("RobotSettingsPlugin registered")

    def create_widget(self) -> AppWidget:
        return RobotSettingsFactory().build(self._service)
