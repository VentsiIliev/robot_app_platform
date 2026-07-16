from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG, PaintProcessConfig


class StubPaintProcessSettingsService(IPaintProcessSettingsService):
    def __init__(self, initial_settings: PaintProcessConfig | None = None):
        self._settings = initial_settings or PAINT_PROCESS_CONFIG

    def load_settings(self) -> PaintProcessConfig:
        return self._settings

    def save_settings(self, settings: PaintProcessConfig) -> None:
        self._settings = settings
        print("Stub: Paint process settings saved")
