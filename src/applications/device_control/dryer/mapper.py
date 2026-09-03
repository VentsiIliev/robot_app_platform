from __future__ import annotations

from src.engine.hardware.dryer.models.dryer_config import DryerConfig


class DryerConfigMapper:
    @staticmethod
    def to_flat_dict(config: DryerConfig) -> dict:
        return config.to_dict()

    @staticmethod
    def from_flat_dict(flat: dict, base: DryerConfig) -> DryerConfig:
        data = base.to_dict()
        data.update(flat)
        return DryerConfig.from_dict(data)
