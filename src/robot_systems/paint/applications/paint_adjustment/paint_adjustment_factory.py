from src.applications.base.application_factory import ApplicationFactory
from .controller.paint_adjustment_controller import PaintAdjustmentController
from .model.paint_adjustment_model import PaintAdjustmentModel
from .view.paint_adjustment_view import PaintAdjustmentView


class PaintAdjustmentFactory(ApplicationFactory):
    def __init__(self) -> None:
        self._messaging = None

    def _create_model(self, service) -> PaintAdjustmentModel:
        return PaintAdjustmentModel(service)

    def _create_view(self) -> PaintAdjustmentView:
        return PaintAdjustmentView()

    def _create_controller(self, model, view) -> PaintAdjustmentController:
        return PaintAdjustmentController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
