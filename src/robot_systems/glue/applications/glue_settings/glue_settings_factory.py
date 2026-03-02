from __future__ import annotations

from src.robot_systems.glue.applications.glue_settings.service.i_glue_settings_service import IGlueSettingsService
from src.robot_systems.glue.applications.glue_settings.model.glue_settings_model import GlueSettingsModel
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.base.application_factory import ApplicationFactory
from src.robot_systems.glue.applications.glue_settings.controller.glue_settings_controller import GlueSettingsController
from src.robot_systems.glue.applications.glue_settings.view.glue_settings_view import GlueSettingsView


class GlueSettingsFactory(ApplicationFactory):

    def _create_model(self, service: IGlueSettingsService) -> IApplicationModel:
        return GlueSettingsModel(service)

    def _create_view(self) -> IApplicationView:
        return GlueSettingsView()

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        return GlueSettingsController(model, view)