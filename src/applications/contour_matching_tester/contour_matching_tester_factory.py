from typing import Optional

from pl_gui.shell.base_app_widget.AppWidget import AppWidget

from src.applications.contour_matching_tester.controller.contour_matching_tester_controller import ContourMatchingTesterController
from src.applications.contour_matching_tester.model.contour_matching_tester_model import ContourMatchingTesterModel
from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService
from src.applications.contour_matching_tester.view.contour_matching_tester_view import ContourMatchingTesterView
from src.engine.core.i_messaging_service import IMessagingService


class ContourMatchingTesterFactory:

    def build(
        self,
        service: IContourMatchingTesterService,
        messaging: Optional[IMessagingService] = None,
    ) -> AppWidget:
        model      = ContourMatchingTesterModel(service)
        view       = ContourMatchingTesterView()
        controller = ContourMatchingTesterController(model, view, messaging)
        controller.load()
        view._controller = controller
        return view
