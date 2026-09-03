from __future__ import annotations

from dataclasses import dataclass

from src.engine.hardware.dryer.models.dryer_commands import DryerCommand
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerDefaults


@dataclass(frozen=True)
class DryerWriteData:
    status: int = DryerDefaults.status
    command: int | DryerCommand = DryerDefaults.command
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

    @classmethod
    def from_config(cls, config: DryerConfig, command: int | DryerCommand = 0) -> "DryerWriteData":
        return cls(command=command, **config.to_dict())

    def to_register_values(self) -> list[int]:
        # Acceleration is stored in tenths in an integer Modbus holding
        # register (for example, 0.1 -> 1). rev_minute is already a raw word.
        acceleration_tenths = round(float(self.acceleration) * 10)
        return [
            int(self.status), int(self.command),
            int(self.pwm_open_vrytka), int(self.pwm_close_vrytka),
            int(self.pwm_open_izbutvatel), int(self.pwm_close_izbutvatel),
            int(self.time_delay_move_servo_up), int(self.time_delay_move_servo_down),
            int(self.time_delay_move_servo_in), int(self.time_delay_move_servo_out),
            int(self.time_delay_move_plate_in), int(self.time_delay_move_plate_out),
            int(self.time_delay_start_servo_move), int(self.rev_minute),
            acceleration_tenths,
            int(self.target_position_backword), int(self.target_position_forword),
        ]
