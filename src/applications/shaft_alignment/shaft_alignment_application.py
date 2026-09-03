import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.applications.base.application_interface import IApplication
from src.applications.shaft_alignment.service.i_shaft_alignment_service import IShaftAlignmentService
from src.applications.shaft_alignment.shaft_alignment_factory import ShaftAlignmentFactory
from src.engine.core.i_messaging_service import IMessagingService


class ShaftAlignmentApplication(IApplication):
    """Optional application entry point; not registered with any robot system."""

    def __init__(self, service: IShaftAlignmentService) -> None:
        self._service = service
        self._logger = logging.getLogger(self.__class__.__name__)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("ShaftAlignmentApplication registered")

    def create_widget(self) -> AppWidget:
        return ShaftAlignmentFactory().build(self._service)
