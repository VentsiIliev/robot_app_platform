from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.glue.applications.workpiece_editor.controller.workpiece_editor_controller import WorkpieceEditorController
from src.robot_systems.glue.applications.workpiece_editor.model import WorkpieceEditorModel
from src.robot_systems.glue.applications.workpiece_editor.service import IWorkpieceEditorService
from src.robot_systems.glue.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView
from src.engine.core.i_messaging_service import IMessagingService


class WorkpieceEditorFactory(ApplicationFactory):

    def __init__(self, messaging: IMessagingService):
        self._messaging = messaging

    def _create_model(self, service: IWorkpieceEditorService) -> WorkpieceEditorModel:
        return WorkpieceEditorModel(service)

    def _create_view(self) -> IApplicationView:
        raise NotImplementedError

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, WorkpieceEditorModel)
        assert isinstance(view, WorkpieceEditorView)
        return WorkpieceEditorController(model, view, self._messaging)

    def build(self, service: IWorkpieceEditorService):
        model      = self._create_model(service)
        glue_types = model.get_glue_types()
        view       = WorkpieceEditorView(glue_types=glue_types)
        controller = self._create_controller(model, view)
        controller.load()
        view._controller = controller
        return view