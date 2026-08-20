from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer


@dataclass(frozen=True)
class DryerConfig:
    """
    Register map and default write values for the dryer board.

    The write block mirrors the firmware ST_MODBUS_WRITE_DATA layout:
    status, command, delay_move_up, delay_move_down, delay_move_in,
    delay_move_out, speed_of_plates.
    """

    status_register: int = 0
    command_register: int = 1
    delay_move_up_register: int = 2
    delay_move_down_register: int = 3
    delay_move_in_register: int = 4
    delay_move_out_register: int = 5
    speed_of_plates_register: int = 6
    default_delay_move_up: int = 0
    default_delay_move_down: int = 0
    default_delay_move_in: int = 0
    default_delay_move_out: int = 0
    default_speed_of_plates: int = 0
    plate_register: int = 2
    open_plate_value: int = 2
    close_plate_value: int = 0

    @property
    def block_start_register(self) -> int:
        return min(self.write_registers)

    @property
    def block_register_count(self) -> int:
        return len(self.write_registers)

    @property
    def write_registers(self) -> tuple[int, ...]:
        return (
            self.status_register,
            self.command_register,
            self.delay_move_up_register,
            self.delay_move_down_register,
            self.delay_move_in_register,
            self.delay_move_out_register,
            self.speed_of_plates_register,
        )

    def require_contiguous_write_block(self) -> None:
        registers = self.write_registers
        expected = tuple(range(registers[0], registers[0] + len(registers)))
        if registers != expected:
            raise ValueError(
                "Dryer registers must be contiguous and ordered for block writes: "
                f"got {registers}, expected {expected}"
            )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DryerConfig":
        return cls(
            status_register=int(data.get("status_register", 0)),
            command_register=int(data.get("command_register", 1)),
            delay_move_up_register=int(data.get("delay_move_up_register", 2)),
            delay_move_down_register=int(data.get("delay_move_down_register", 3)),
            delay_move_in_register=int(data.get("delay_move_in_register", 4)),
            delay_move_out_register=int(data.get("delay_move_out_register", 5)),
            speed_of_plates_register=int(data.get("speed_of_plates_register", 6)),
            default_delay_move_up=int(data.get("default_delay_move_up", 0)),
            default_delay_move_down=int(data.get("default_delay_move_down", 0)),
            default_delay_move_in=int(data.get("default_delay_move_in", 0)),
            default_delay_move_out=int(data.get("default_delay_move_out", 0)),
            default_speed_of_plates=int(data.get("default_speed_of_plates", 0)),
            plate_register=int(data.get("plate_register", 2)),
            open_plate_value=int(data.get("open_plate_value", 2)),
            close_plate_value=int(data.get("close_plate_value", 0)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DryerConfigSerializer(ISettingsSerializer[DryerConfig]):
    @property
    def settings_type(self) -> str:
        return "dryer_config"

    def get_default(self) -> DryerConfig:
        return DryerConfig()

    def to_dict(self, settings: DryerConfig) -> Dict[str, Any]:
        return settings.to_dict()

    def from_dict(self, data: Dict[str, Any]) -> DryerConfig:
        return DryerConfig.from_dict(data)
