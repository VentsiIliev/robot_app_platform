from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerDefaults
from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass(frozen=True)
class DryerConfig:
    """Editable values for the current dryer firmware register block."""

    pwm_open_vrytka: int = DryerDefaults.pwm_open_vrytka
    pwm_close_vrytka: int = DryerDefaults.pwm_close_vrytka
    pwm_open_izbutvatel: int = DryerDefaults.pwm_open_izbutvatel
    pwm_close_izbutvatel: int = DryerDefaults.pwm_close_izbutvatel
    time_delay_move_servo_up: int = DryerDefaults.time_delay_move_servo_up
    time_delay_move_servo_down: int = DryerDefaults.time_delay_move_servo_down
    time_delay_move_servo_in: int = DryerDefaults.time_delay_move_servo_in
    time_delay_move_servo_out: int = DryerDefaults.time_delay_move_servo_out
    time_delay_move_plate_in: int = DryerDefaults.time_delay_move_plate_in
    time_delay_move_plate_out: int = DryerDefaults.time_delay_move_plate_out
    time_delay_start_servo_move: int = DryerDefaults.time_delay_start_servo_move
    rev_minute: int = DryerDefaults.rev_minute
    acceleration: float = DryerDefaults.acceleration
    target_position_backword: int = DryerDefaults.target_position_backword
    target_position_forword: int = DryerDefaults.target_position_forword
    target_position_next_position: int = DryerDefaults.target_position_next_position

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DryerConfig":
        defaults = cls()
        values: dict[str, int | float] = {}
        for name in cls.__dataclass_fields__:
            raw = data.get(name, getattr(defaults, name))
            values[name] = float(raw) if name == "acceleration" else int(raw)
        return cls(**values)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DryerConfigSerializer(ISettingsSerializer[DryerConfig]):
    @property
    def settings_type(self) -> str:
        return "dryer_config"

    def get_default(self) -> DryerConfig:
        return DryerConfig()

    def to_dict(self, settings: DryerConfig) -> dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: dict[str, Any]) -> DryerConfig:
        return DryerConfig.from_dict(data)
