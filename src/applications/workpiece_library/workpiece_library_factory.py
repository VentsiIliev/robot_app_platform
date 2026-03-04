from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.workpiece_library.controller.workpiece_library_controller import WorkpieceLibraryController
from src.applications.workpiece_library.model.workpiece_library_model import WorkpieceLibraryModel
from src.applications.workpiece_library.service.i_workpiece_library_service import IWorkpieceLibraryService
from src.applications.workpiece_library.view.workpiece_library_view import WorkpieceLibraryView
from src.engine.core.i_messaging_service import IMessagingService


class WorkpieceLibraryFactory(ApplicationFactory):

    def _create_model(self, service: IWorkpieceLibraryService) -> WorkpieceLibraryModel:
        return WorkpieceLibraryModel(service)

    def _create_view(self) -> IApplicationView:
        raise NotImplementedError("Use build() — view requires schema from model")

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, WorkpieceLibraryModel)
        assert isinstance(view, WorkpieceLibraryView)
        return WorkpieceLibraryController(model, view)

    def build(self, service: IWorkpieceLibraryService, messaging: IMessagingService = None):
        model      = self._create_model(service)
        view       = WorkpieceLibraryView(schema=model.schema)
        controller = WorkpieceLibraryController(model, view, messaging)
        controller.load()
        view._controller = controller
        return view