import logging
from typing import Optional

from src.applications.base.application_factory import finalize_application_build
from src.applications.pick_and_place_visualizer.controller.pick_and_place_visualizer_controller import (
    PickAndPlaceVisualizerController,
)
from src.applications.pick_and_place_visualizer.model.pick_and_place_visualizer_model import (
    PickAndPlaceVisualizerModel,
)
from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import (
    IPickAndPlaceVisualizerService,
)
from src.applications.pick_and_place_visualizer.view.pick_and_place_visualizer_view import (
    PickAndPlaceVisualizerView,
)
from src.engine.core.i_messaging_service import IMessagingService


class PickAndPlaceVisualizerFactory:
    _logger = logging.getLogger("PickAndPlaceVisualizerFactory")

    def build(
        self,
        service:   IPickAndPlaceVisualizerService,
        messaging: Optional[IMessagingService] = None,
        jog_service=None,
    ):
        model      = PickAndPlaceVisualizerModel(service)
        view       = PickAndPlaceVisualizerView()
        controller = PickAndPlaceVisualizerController(model, view, messaging)
        return finalize_application_build(
            logger=self._logger,
            factory_name=self.__class__.__name__,
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )
