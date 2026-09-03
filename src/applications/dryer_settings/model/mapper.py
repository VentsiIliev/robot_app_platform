from __future__ import annotations

from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData


class DryerSettingsMapper:
    @staticmethod
    def to_flat_dict(config: DryerConfig) -> dict:
        return config.to_dict()

    @staticmethod
    def from_flat_dict(flat: dict, base: DryerConfig) -> DryerConfig:
        data = base.to_dict()
        data.update(flat)
        return DryerConfig.from_dict(data)

    @staticmethod
    def write_data_from_flat(flat: dict) -> DryerWriteData:
        return DryerWriteData.from_config(DryerConfig.from_dict(flat))
