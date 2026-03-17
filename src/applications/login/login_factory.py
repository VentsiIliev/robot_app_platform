from src.applications.login.controller.login_controller import LoginController
from src.applications.login.i_login_application_service import ILoginApplicationService
from src.applications.login.model.login_model import LoginModel
from src.applications.login.view.login_view import LoginView


class LoginFactory:
    """Builds and wires the login MVC triple, returns the dialog."""

    @staticmethod
    def build(service: ILoginApplicationService, parent=None) -> LoginView:
        model  = LoginModel(service)
        view   = LoginView(parent)
        ctrl   = LoginController(model, view)
        # Keep controller alive as long as the view (same pattern as ApplicationFactory)
        view._controller = ctrl
        ctrl.load()
        return view
