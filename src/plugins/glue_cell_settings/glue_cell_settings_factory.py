from __future__ import annotations

from src.engine.core.i_messaging_service import IMessagingService
from src.plugins.base.i_plugin_controller import IPluginController
from src.plugins.base.i_plugin_model import IPluginModel
from src.plugins.base.i_plugin_view import IPluginView
from src.plugins.glue_cell_settings.controller.glue_cell_settings_controller import GlueCellSettingsController
from src.plugins.glue_cell_settings.model.glue_cell_settings_model import GlueCellSettingsModel
from src.plugins.glue_cell_settings.service.i_glue_cell_settings_service import IGlueCellSettingsService
from src.plugins.glue_cell_settings.view.glue_cell_settings_view import GlueCellSettingsView


class GlueCellSettingsFactory:

    def build(self, service: IGlueCellSettingsService, messaging: IMessagingService):
        cell_ids   = service.get_cell_ids()
        model      = GlueCellSettingsModel(service)
        view       = GlueCellSettingsView(cell_ids)
        controller = GlueCellSettingsController(model, view, messaging)
        controller.load()
        view._controller = controller
        return view