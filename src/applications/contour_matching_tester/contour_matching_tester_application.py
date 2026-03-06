import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.applications.base.application_interface import IApplication
from src.applications.contour_matching_tester.contour_matching_tester_factory import ContourMatchingTesterFactory
from src.applications.contour_matching_tester.service.contour_matching_tester_service import ContourMatchingTesterService


class ContourMatchingTesterApplication(IApplication):

    def __init__(self, vision_service=None, workpiece_service=None):
        self._logger  = logging.getLogger(self.__class__.__name__)
        self._service = ContourMatchingTesterService(vision_service, workpiece_service)

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("ContourMatchingTesterApplication registered")

    def create_widget(self) -> AppWidget:
        return ContourMatchingTesterFactory().build(self._service)

