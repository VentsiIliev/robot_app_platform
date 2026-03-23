from src.applications.base.application_factory import ApplicationFactory
from src.applications.pick_target.controller.pick_target_controller import PickTargetController
from src.applications.pick_target.model.pick_target_model import PickTargetModel
from src.applications.pick_target.service.i_pick_target_service import IPickTargetService
from src.applications.pick_target.view.pick_target_view import PickTargetView


class PickTargetFactory(ApplicationFactory):

    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IPickTargetService) -> PickTargetModel:
        return PickTargetModel(service)

    def _create_view(self) -> PickTargetView:
        return PickTargetView()

    def _create_controller(self, model: PickTargetModel, view: PickTargetView) -> PickTargetController:
        return PickTargetController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
