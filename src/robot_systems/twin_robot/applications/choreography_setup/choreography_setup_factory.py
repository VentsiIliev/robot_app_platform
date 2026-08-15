from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.robot_systems.twin_robot.applications.choreography_setup.controller.choreography_setup_controller import (
    ChoreographySetupController,
)
from src.robot_systems.twin_robot.applications.choreography_setup.model.choreography_setup_model import (
    ChoreographySetupModel,
)
from src.robot_systems.twin_robot.applications.choreography_setup.service.i_choreography_setup_service import (
    IChoreographySetupService,
)
from src.robot_systems.twin_robot.applications.choreography_setup.view.choreography_setup_view import (
    ChoreographySetupView,
)


class ChoreographySetupFactory(ApplicationFactory):
    def _create_model(self, service: IChoreographySetupService) -> IApplicationModel:
        return ChoreographySetupModel(service)

    def _create_view(self) -> IApplicationView:
        return ChoreographySetupView()

    def _create_controller(
        self,
        model: IApplicationModel,
        view: IApplicationView,
    ) -> IApplicationController:
        return ChoreographySetupController(model, view)
