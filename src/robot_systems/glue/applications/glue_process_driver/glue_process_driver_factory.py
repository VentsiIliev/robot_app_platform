from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.engine.core.i_messaging_service import IMessagingService
from src.robot_systems.glue.applications.glue_process_driver.controller.glue_process_driver_controller import (
    GlueProcessDriverController,
)
from src.robot_systems.glue.applications.glue_process_driver.model.glue_process_driver_model import (
    GlueProcessDriverModel,
)
from src.robot_systems.glue.applications.glue_process_driver.service.i_glue_process_driver_service import (
    IGlueProcessDriverService,
)
from src.robot_systems.glue.applications.glue_process_driver.view.glue_process_driver_view import (
    GlueProcessDriverView,
)


class GlueProcessDriverFactory(ApplicationFactory):
    def __init__(self, broker: IMessagingService | None = None):
        self._broker = broker

    def _create_model(self, service: IGlueProcessDriverService) -> IApplicationModel:
        return GlueProcessDriverModel(service)

    def _create_view(self) -> IApplicationView:
        return GlueProcessDriverView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return GlueProcessDriverController(model, view, self._broker)
