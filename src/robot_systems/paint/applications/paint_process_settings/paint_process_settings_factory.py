from src.applications.base.application_factory import ApplicationFactory
from src.robot_systems.paint.applications.paint_process_settings.controller.paint_process_settings_controller import (
    PaintProcessSettingsController,
)
from src.robot_systems.paint.applications.paint_process_settings.model.paint_process_settings_model import (
    PaintProcessSettingsModel,
)
from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_view import (
    PaintProcessSettingsView,
)


class PaintProcessSettingsFactory(ApplicationFactory):
    def _create_model(self, service: IPaintProcessSettingsService) -> PaintProcessSettingsModel:
        return PaintProcessSettingsModel(service)

    def _create_view(self) -> PaintProcessSettingsView:
        return PaintProcessSettingsView()

    def _create_controller(
        self,
        model: PaintProcessSettingsModel,
        view: PaintProcessSettingsView,
    ) -> PaintProcessSettingsController:
        return PaintProcessSettingsController(model, view)

    def build(self, service: IPaintProcessSettingsService, messaging=None, jog_service=None):
        return super().build(service, messaging=messaging, jog_service=jog_service)
