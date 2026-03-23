import logging
from typing import Optional

from pl_gui.shell.base_app_widget.AppWidget import AppWidget

from src.applications.base.application_factory import finalize_application_build
from src.applications.contour_matching_tester.controller.contour_matching_tester_controller import ContourMatchingTesterController
from src.applications.contour_matching_tester.model.contour_matching_tester_model import ContourMatchingTesterModel
from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService
from src.applications.contour_matching_tester.view.contour_matching_tester_view import ContourMatchingTesterView
from src.engine.core.i_messaging_service import IMessagingService


class ContourMatchingTesterFactory:
    _logger = logging.getLogger("ContourMatchingTesterFactory")

    def build(
        self,
        service: IContourMatchingTesterService,
        messaging: Optional[IMessagingService] = None,
        jog_service=None,
    ) -> AppWidget:
        model      = ContourMatchingTesterModel(service)
        view       = ContourMatchingTesterView()
        controller = ContourMatchingTesterController(model, view, messaging)
        return finalize_application_build(
            logger=self._logger,
            factory_name=self.__class__.__name__,
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )
