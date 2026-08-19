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
        return DryerWriteData(
            delay_move_up=int(flat.get("default_delay_move_up", 0)),
            delay_move_down=int(flat.get("default_delay_move_down", 0)),
            delay_move_in=int(flat.get("default_delay_move_in", 0)),
            delay_move_out=int(flat.get("default_delay_move_out", 0)),
            speed_of_plates=int(flat.get("default_speed_of_plates", 0)),
        )
