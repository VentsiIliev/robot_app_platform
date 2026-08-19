from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.dryer_settings.controller.dryer_settings_controller import DryerSettingsController
from src.applications.dryer_settings.model.dryer_settings_model import DryerSettingsModel
from src.applications.dryer_settings.service.i_dryer_settings_service import IDryerSettingsService
from src.applications.dryer_settings.view.dryer_settings_view import DryerSettingsView


class DryerSettingsFactory(ApplicationFactory):
    def _create_model(self, service: IDryerSettingsService) -> IApplicationModel:
        return DryerSettingsModel(service)

    def _create_view(self) -> IApplicationView:
        return DryerSettingsView()

    def _create_controller(
        self,
        model: IApplicationModel,
        view: IApplicationView,
    ) -> IApplicationController:
        return DryerSettingsController(model, view)
