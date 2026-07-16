from src.applications.base.i_application_model import IApplicationModel
from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class PaintProcessSettingsModel(IApplicationModel):
    def __init__(self, service: IPaintProcessSettingsService):
        self._service = service
        self._settings: PaintProcessConfig | None = None

    def load(self) -> PaintProcessConfig:
        self._settings = self._service.load_settings()
        return self._settings

    def save(self, settings: PaintProcessConfig) -> None:
        self._service.save_settings(settings)
        self._settings = settings

    @property
    def current_settings(self) -> PaintProcessConfig:
        if self._settings is None:
            self._settings = self._service.load_settings()
        return self._settings
