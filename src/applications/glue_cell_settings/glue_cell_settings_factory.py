from __future__ import annotations

from src.engine.core.i_messaging_service import IMessagingService
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.glue_cell_settings.controller.glue_cell_settings_controller import GlueCellSettingsController
from src.applications.glue_cell_settings.model.glue_cell_settings_model import GlueCellSettingsModel
from src.applications.glue_cell_settings.service.i_glue_cell_settings_service import IGlueCellSettingsService
from src.applications.glue_cell_settings.view.glue_cell_settings_view import GlueCellSettingsView


class GlueCellSettingsFactory:

    def build(self, service: IGlueCellSettingsService, messaging: IMessagingService):
        cell_ids   = service.get_cell_ids()
        model      = GlueCellSettingsModel(service)
        view       = GlueCellSettingsView(cell_ids)
        controller = GlueCellSettingsController(model, view, messaging)
        controller.load()
        view._controller = controller
        return view