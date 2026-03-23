from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.height_measuring.controller.height_measuring_controller import HeightMeasuringController
from src.applications.height_measuring.model.height_measuring_model import HeightMeasuringModel
from src.applications.height_measuring.service.i_height_measuring_app_service import IHeightMeasuringAppService
from src.applications.height_measuring.view.height_measuring_view import HeightMeasuringView


class HeightMeasuringFactory(ApplicationFactory):
    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IHeightMeasuringAppService) -> HeightMeasuringModel:
        return HeightMeasuringModel(service)

    def _create_view(self) -> HeightMeasuringView:
        return HeightMeasuringView()

    def _create_controller(self, model: HeightMeasuringModel, view: HeightMeasuringView) -> IApplicationController:
        return HeightMeasuringController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
