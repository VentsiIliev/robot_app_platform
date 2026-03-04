from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from .controller.tool_settings_controller import ToolSettingsController
from .model.tool_settings_model import ToolSettingsModel
from .service.i_tool_settings_service import IToolSettingsService
from .view.tool_settings_view import ToolSettingsView


class ToolSettingsFactory(ApplicationFactory):

    def _create_model(self, service: IToolSettingsService) -> ToolSettingsModel:
        return ToolSettingsModel(service)

    def _create_view(self) -> IApplicationView:
        return ToolSettingsView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return ToolSettingsController(model, view)