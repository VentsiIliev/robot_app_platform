from __future__ import annotations

from dataclasses import dataclass

from src.engine.hardware.dryer.models.dryer_commands import DryerCommand


@dataclass(frozen=True)
class DryerWriteData:
    status: int = 0
    command: int | DryerCommand = 0
    delay_move_up: int = 0
    delay_move_down: int = 0
    delay_move_in: int = 0
    delay_move_out: int = 0
    speed_of_plates: int = 0

    def to_register_values(self) -> list[int]:
        return [
            int(self.status),
            int(self.command),
            int(self.delay_move_up),
            int(self.delay_move_down),
            int(self.delay_move_in),
            int(self.delay_move_out),
            int(self.speed_of_plates),
        ]
