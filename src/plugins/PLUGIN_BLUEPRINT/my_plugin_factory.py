from __future__ import annotations

from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView
from src.plugins.base.plugin_factory import PluginFactory
from src.plugins.PLUGIN_BLUEPRINT.controller.my_controller import MyController
from src.plugins.PLUGIN_BLUEPRINT.model.my_model import MyModel
from src.plugins.PLUGIN_BLUEPRINT.service.i_my_service import IMyService
from src.plugins.PLUGIN_BLUEPRINT.view.my_view import MyView


class MyPluginFactory(PluginFactory):

    def _create_model(self, service: IMyService) -> IPluginModel:
        return MyModel(service)

    def _create_view(self) -> IPluginView:
        return MyView()

    def _create_controller(self, model: IPluginModel, view: IPluginView) -> IPluginController:
        return MyController(model, view)
