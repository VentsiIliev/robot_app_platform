from typing import Optional

from src.applications.base.application_factory import ApplicationFactory
from src.applications.pick_target.controller.pick_target_controller import PickTargetController
from src.applications.pick_target.model.pick_target_model import PickTargetModel
from src.applications.pick_target.service.i_pick_target_service import IPickTargetService
from src.applications.pick_target.view.pick_target_view import PickTargetView
from src.engine.core.i_messaging_service import IMessagingService


class PickTargetFactory(ApplicationFactory):

    def __init__(self, messaging: Optional[IMessagingService] = None):
        self._messaging = messaging

    def _create_model(self, service: IPickTargetService) -> PickTargetModel:
        return PickTargetModel(service)

    def _create_view(self) -> PickTargetView:
        return PickTargetView()

    def _create_controller(self, model: PickTargetModel, view: PickTargetView) -> PickTargetController:
        return PickTargetController(model, view, self._messaging)
