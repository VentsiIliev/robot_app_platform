from __future__ import annotations

import logging

from src.applications.base.i_application_model import IApplicationModel
from src.applications.dryer_settings.model.mapper import DryerSettingsMapper
from src.applications.dryer_settings.service.i_dryer_settings_service import IDryerSettingsService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState


class DryerSettingsModel(IApplicationModel):
    def __init__(self, service: IDryerSettingsService) -> None:
        self._service = service
        self._config: DryerConfig | None = None
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> DryerConfig:
        self._config = self._service.load_config()
        return self._config

    def save(self, flat: dict, **kwargs) -> None:
        updated = self.config_from_flat(flat)
        self._service.save_config(updated)
        self._config = updated
        self._logger.info("Dryer config saved")

    def config_from_flat(self, flat: dict) -> DryerConfig:
        base = self._config if self._config is not None else DryerConfig()
        return DryerSettingsMapper.from_flat_dict(flat, base)

    def get_state(self, flat: dict) -> DryerState:
        config = self.config_from_flat(flat)
        return self._service.get_state(config)

    def move_servos(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.move_servos(
            config,
            DryerSettingsMapper.write_data_from_flat(flat),
        )

    def open_plate(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.open_plate(
            config,
            DryerSettingsMapper.write_data_from_flat(flat),
        )

    def close_plate(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.close_plate(
            config,
            DryerSettingsMapper.write_data_from_flat(flat),
        )

    def next_position(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.next_position(
            config,
            DryerSettingsMapper.write_data_from_flat(flat),
        )
