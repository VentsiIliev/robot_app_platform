import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.plugins.base.plugin_interface import IPlugin
from src.plugins.PLUGIN_BLUEPRINT.my_plugin_factory import MyPluginFactory
from src.plugins.PLUGIN_BLUEPRINT.service.my_plugin_service import MyPluginService


class MyPlugin(IPlugin):

    def __init__(self, settings_service=None):
        self._logger  = logging.getLogger(self.__class__.__name__)
        self._service = MyPluginService(settings_service)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("MyPlugin registered")

    def create_widget(self) -> AppWidget:
        return MyPluginFactory().build(self._service)
