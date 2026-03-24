from __future__ import annotations

from src.applications.base.application_factory import ApplicationFactory
from src.applications.base.i_application_controller import IApplicationController
from src.applications.base.i_application_model import IApplicationModel
from src.applications.base.i_application_view import IApplicationView
from src.applications.work_area_settings.controller.work_area_settings_controller import (
    WorkAreaSettingsController,
)
from src.applications.work_area_settings.model.work_area_settings_model import (
    WorkAreaSettingsModel,
)
from src.applications.work_area_settings.service.i_work_area_settings_service import (
    IWorkAreaSettingsService,
)
from src.applications.work_area_settings.view.work_area_settings_view import (
    WorkAreaSettingsView,
)
from src.shared_contracts.declarations import WorkAreaDefinition


class WorkAreaSettingsFactory(ApplicationFactory):
    def __init__(self, work_area_definitions: list[WorkAreaDefinition] | None = None):
        self._messaging = None
        self._work_area_definitions = list(work_area_definitions or [])

    def _create_model(self, service: IWorkAreaSettingsService) -> WorkAreaSettingsModel:
        return WorkAreaSettingsModel(service)

    def _create_view(self) -> WorkAreaSettingsView:
        return WorkAreaSettingsView(work_area_definitions=self._work_area_definitions)

    def _create_controller(self, model: IApplicationModel, view: IApplicationView) -> IApplicationController:
        assert isinstance(model, WorkAreaSettingsModel)
        assert isinstance(view, WorkAreaSettingsView)
        return WorkAreaSettingsController(model, view, self._messaging)

    def build(self, service, messaging=None, jog_service=None):
        self._messaging = messaging
        return super().build(service, messaging=messaging, jog_service=jog_service)
