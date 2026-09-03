from src.applications.base.application_factory import ApplicationFactory
from src.applications.shaft_alignment.controller.shaft_alignment_controller import ShaftAlignmentController
from src.applications.shaft_alignment.model.shaft_alignment_model import ShaftAlignmentModel
from src.applications.shaft_alignment.service.i_shaft_alignment_service import IShaftAlignmentService
from src.applications.shaft_alignment.view.shaft_alignment_view import ShaftAlignmentView


class ShaftAlignmentFactory(ApplicationFactory):
    def _create_model(self, service: IShaftAlignmentService) -> ShaftAlignmentModel:
        return ShaftAlignmentModel(service)

    def _create_view(self) -> ShaftAlignmentView:
        return ShaftAlignmentView()

    def _create_controller(self, model, view) -> ShaftAlignmentController:
        return ShaftAlignmentController(model, view)
