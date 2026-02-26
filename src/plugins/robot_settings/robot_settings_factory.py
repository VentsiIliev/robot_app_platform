from __future__ import annotations

from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView
from src.plugins.base.plugin_factory import PluginFactory
from src.plugins.robot_settings.controller.robot_settings_controller import RobotSettingsController
from src.plugins.robot_settings.model.robot_settings_model import RobotSettingsModel
from src.plugins.robot_settings.service.i_robot_settings_service import IRobotSettingsService
from src.plugins.robot_settings.view.robot_settings_view import RobotSettingsView


class RobotSettingsFactory(PluginFactory):

    def _create_model(self, service: IRobotSettingsService) -> IPluginModel:
        return RobotSettingsModel(service)

    def _create_view(self) -> IPluginView:
        return RobotSettingsView()

    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController:
        return RobotSettingsController(model, view)
