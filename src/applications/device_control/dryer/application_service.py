from __future__ import annotations

from enum import Enum

from src.applications.device_control.dryer.service import IDryerControlService
from src.engine.hardware.dryer.interfaces.i_dryer_service import IDryerService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.repositories.interfaces.i_settings_service import ISettingsService


class DryerControlService(IDryerControlService):
    """Persists dryer configuration and updates the live controller."""

    def __init__(
        self,
        settings_service: ISettingsService,
        dryer_config_key: Enum,
        live_controller: IDryerService | None = None,
    ) -> None:
        self._settings = settings_service
        self._dryer_config_key = dryer_config_key
        self._live_controller = live_controller

    def load_config(self) -> DryerConfig:
        config = self._settings.get(self._dryer_config_key)
        if not isinstance(config, DryerConfig):
            raise TypeError("Dryer settings are unavailable")
        return config

    def save_config(self, config: DryerConfig) -> None:
        self._settings.save(self._dryer_config_key, config)
        if self._live_controller is not None:
            self._live_controller.update_config(config)
