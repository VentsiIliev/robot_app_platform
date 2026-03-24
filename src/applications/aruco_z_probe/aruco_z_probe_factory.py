from src.applications.base.application_factory import ApplicationFactory
from src.applications.aruco_z_probe.controller.aruco_z_probe_controller import ArucoZProbeController
from src.applications.aruco_z_probe.model.aruco_z_probe_model import ArucoZProbeModel
from src.applications.aruco_z_probe.service.i_aruco_z_probe_service import IArucoZProbeService
from src.applications.aruco_z_probe.view.aruco_z_probe_view import ArucoZProbeView


class ArucoZProbeFactory(ApplicationFactory):

    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IArucoZProbeService) -> ArucoZProbeModel:
        return ArucoZProbeModel(service)

    def _create_view(self) -> ArucoZProbeView:
        return ArucoZProbeView()

    def _create_controller(self, model: ArucoZProbeModel, view: ArucoZProbeView) -> ArucoZProbeController:
        return ArucoZProbeController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
