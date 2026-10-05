from src.applications.base.application_factory import ApplicationFactory
from .model.software_update_model import SoftwareUpdateModel
from .view.software_update_view import SoftwareUpdateView
from .controller.software_update_controller import SoftwareUpdateController


class SoftwareUpdateFactory(ApplicationFactory):
    def _create_model(self, service): return SoftwareUpdateModel(service)
    def _create_view(self): return SoftwareUpdateView()
    def _create_controller(self, model, view): return SoftwareUpdateController(model, view)
