from __future__ import annotations

import logging

from src.applications.base.i_application_model import IApplicationModel
from src.applications.device_control.dryer.mapper import DryerConfigMapper
from src.applications.device_control.dryer.service import IDryerControlService
from src.engine.hardware.dryer.models.dryer_config import DryerConfig


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
