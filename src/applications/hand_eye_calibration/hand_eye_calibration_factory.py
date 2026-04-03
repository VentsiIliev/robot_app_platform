from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.hand_eye_calibration.controller.hand_eye_controller import HandEyeController
from src.applications.hand_eye_calibration.model.hand_eye_model import HandEyeModel
from src.applications.hand_eye_calibration.view.hand_eye_view import HandEyeView


class HandEyeCalibrationFactory(ApplicationFactory):

    def __init__(self, messaging=None):
        self._messaging = messaging

    def _create_model(self, service) -> IApplicationModel:
        return HandEyeModel(service)

    def _create_view(self) -> IApplicationView:
        return HandEyeView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return HandEyeController(model, view, messaging=self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
