import logging

from pl_gui.shell.base_app_widget.AppWidget import AppWidget
from src.engine.common_settings_ids import CommonSettingsID
from src.engine.core.i_messaging_service import IMessagingService
from src.engine.repositories.interfaces.i_settings_service import ISettingsService
from src.applications.base.application_interface import IApplication
from src.applications.robot_settings.robot_settings_factory import RobotSettingsFactory
from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService


class RobotSettingsApplication(IApplication):

    def __init__(self, settings_service: ISettingsService):
        self._logger  = logging.getLogger(self.__class__.__name__)
        self._service = RobotSettingsApplicationService(
            settings_service,
            config_key=CommonSettingsID.ROBOT_CONFIG,
            movement_groups_key=CommonSettingsID.MOVEMENT_GROUPS,
            calibration_key=CommonSettingsID.ROBOT_CALIBRATION,
        )

    def register(self, messaging_service: IMessagingService) -> None:
        self._logger.debug("RobotSettingsApplication registered")

    def create_widget(self) -> AppWidget:
        return RobotSettingsFactory().build(self._service)
