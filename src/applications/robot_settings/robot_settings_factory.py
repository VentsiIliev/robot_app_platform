from __future__ import annotations

from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.application_factory import ApplicationFactory
from src.applications.robot_settings.controller.robot_settings_controller import RobotSettingsController
from src.applications.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.applications.robot_settings.service.i_robot_settings_service import IRobotSettingsService
from src.applications.robot_settings.view.robot_settings_view import RobotSettingsView


from src.applications.base.robot_jog_service import RobotJogService
from src.engine.core.i_messaging_service import IMessagingService


class RobotSettingsFactory(ApplicationFactory):

    def __init__(self, messaging: IMessagingService, jog_service: RobotJogService):
        self._messaging   = messaging
        self._jog_service = jog_service

    def _create_model(self, service: IRobotSettingsService) -> IApplicationModel:
        return RobotSettingsModel(service)

    def _create_view(self) -> IApplicationView:
        return RobotSettingsView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return RobotSettingsController(model, view, self._messaging, self._jog_service)
