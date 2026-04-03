from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.intrinsic_calibration_capture.controller.intrinsic_capture_controller import (
    IntrinsicCaptureController,
)
from src.applications.intrinsic_calibration_capture.model.intrinsic_capture_model import IntrinsicCaptureModel
from src.applications.intrinsic_calibration_capture.view.intrinsic_capture_view import IntrinsicCaptureView


class IntrinsicCaptureFactory(ApplicationFactory):

    def __init__(self, messaging=None):
        self._messaging = messaging

    def _create_model(self, service) -> IApplicationModel:
        return IntrinsicCaptureModel(service)

    def _create_view(self) -> IApplicationView:
        return IntrinsicCaptureView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return IntrinsicCaptureController(model, view, messaging=self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
