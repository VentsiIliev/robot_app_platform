from __future__ import annotations

from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.application_factory import ApplicationFactory
from src.applications.APPLICATION_BLUEPRINT.controller.my_controller import MyController
from src.applications.APPLICATION_BLUEPRINT.model.my_model import MyModel
from src.applications.APPLICATION_BLUEPRINT.service.i_my_service import IMyService
from src.applications.APPLICATION_BLUEPRINT.view.my_view import MyView


class MyApplicationFactory(ApplicationFactory):

    def _create_model(self, service: IMyService) -> IApplicationModel:
        return MyModel(service)

    def _create_view(self) -> IApplicationView:
        return MyView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return MyController(model, view)
