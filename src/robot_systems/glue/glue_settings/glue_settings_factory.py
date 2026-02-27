from __future__ import annotations

from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView
from src.plugins.base.plugin_factory import PluginFactory
from src.robot_systems.glue.glue_settings.controller.glue_settings_controller import GlueSettingsController
from src.robot_systems.glue.glue_settings.model.glue_settings_model import GlueSettingsModel
from src.robot_systems.glue.glue_settings.service.i_glue_settings_service import IGlueSettingsService
from src.robot_systems.glue.glue_settings.view.glue_settings_view import GlueSettingsView


class GlueSettingsFactory(PluginFactory):

    def _create_model(self, service: IGlueSettingsService) -> IPluginModel:
        return GlueSettingsModel(service)

    def _create_view(self) -> IPluginView:
        return GlueSettingsView()

    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController:
        return GlueSettingsController(model, view)