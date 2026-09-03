from __future__ import annotations

import logging

from src.applications.base.i_application_model import IApplicationModel
from src.applications.device_control.dryer.mapper import DryerConfigMapper
from src.applications.device_control.dryer.service import IDryerControlService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_state import DryerState


class DryerControlModel(IApplicationModel):
    def __init__(self, service: IDryerControlService) -> None:
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
        return DryerConfigMapper.from_flat_dict(flat, base)

    def get_state(self, flat: dict) -> DryerState:
        config = self.config_from_flat(flat)
        return self._service.get_state(config)

    def move_servos(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.move_servos(
            config,
            DryerConfigMapper.write_data_from_flat(flat),
        )

    def open_plate(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.open_plate(
            config,
            DryerConfigMapper.write_data_from_flat(flat),
        )

    def close_plate(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.close_plate(
            config,
            DryerConfigMapper.write_data_from_flat(flat),
        )

    def next_position(self, flat: dict) -> bool:
        config = self.config_from_flat(flat)
        return self._service.next_position(
            config,
            DryerConfigMapper.write_data_from_flat(flat),
        )
