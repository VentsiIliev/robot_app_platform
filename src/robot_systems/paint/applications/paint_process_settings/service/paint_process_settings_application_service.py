from src.robot_systems.paint.applications.paint_process_settings.service.i_paint_process_settings_service import (
    IPaintProcessSettingsService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig
from src.robot_systems.paint.processes.paint.paint_process_config_service import (
    IPaintProcessConfigService,
)


class PaintProcessSettingsApplicationService(IPaintProcessSettingsService):
    def __init__(self, process_config_service: IPaintProcessConfigService):
        self._process_config_service = process_config_service

    def load_settings(self) -> PaintProcessConfig:
        return self._process_config_service.get_snapshot()

    def save_settings(self, settings: PaintProcessConfig) -> None:
        self._process_config_service.save(settings)
