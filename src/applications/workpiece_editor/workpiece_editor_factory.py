from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.workpiece_editor.controller.workpiece_editor_controller import WorkpieceEditorController
from src.applications.workpiece_editor.model import WorkpieceEditorModel
from src.applications.workpiece_editor.service import IWorkpieceEditorService
from src.applications.workpiece_editor.view.workpiece_editor_view import WorkpieceEditorView


class WorkpieceEditorFactory(ApplicationFactory):
    def __init__(self):
        self._messaging = None

    def _create_model(self, service: IWorkpieceEditorService) -> WorkpieceEditorModel:
        return WorkpieceEditorModel(service)

    def _create_view(self) -> IApplicationView:
        raise NotImplementedError("Use build() directly")

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, WorkpieceEditorModel)
        assert isinstance(view, WorkpieceEditorView)
        return WorkpieceEditorController(model, view, self._messaging)

    def build(self, service: IWorkpieceEditorService, messaging=None, jog_service=None):
        self._messaging = messaging
        schema = service.get_form_schema()
        segment_config = service.get_segment_config()
        model = self._create_model(service)
        view = WorkpieceEditorView(schema=schema, segment_config=segment_config)
        controller = self._create_controller(model, view)
        return self._finalize_build(
            model=model,
            view=view,
            controller=controller,
            messaging=messaging,
            jog_service=jog_service,
        )
