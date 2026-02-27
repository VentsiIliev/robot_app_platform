import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.applications.base.application_interface import IApplication
from src.applications.APPLICATION_BLUEPRINT.my_application_factory import MyApplicationFactory
from src.applications.APPLICATION_BLUEPRINT.service.my_application_service import MyApplicationService


class MyApplication(IApplication):

    def __init__(self, settings_service=None):
        self._logger  = logging.getLogger(self.__class__.__name__)
        self._service = MyApplicationService(settings_service)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("MyApplication registered")

    def create_widget(self) -> AppWidget:
        return MyApplicationFactory().build(self._service)
