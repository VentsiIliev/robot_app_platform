from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.user_management.controller.user_management_controller import UserManagementController
from src.applications.user_management.model.user_management_model import UserManagementModel
from src.applications.user_management.service.i_user_management_service import IUserManagementService
from src.applications.user_management.view.user_management_view import UserManagementView


class UserManagementFactory(ApplicationFactory):

    def _create_model(self, service: IUserManagementService) -> UserManagementModel:
        return UserManagementModel(service)

    def _create_view(self) -> IApplicationView:
        # schema is not available until _create_model runs, so the view is built lazily in build()
        raise NotImplementedError("Use build() directly — view needs the model's schema")

    def build(self, service: IUserManagementService):
        model      = self._create_model(service)
        view       = UserManagementView(schema=model.schema)
        controller = UserManagementController(model, view)
        controller.load()
        view._controller = controller
        return view

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return UserManagementController(model, view)
