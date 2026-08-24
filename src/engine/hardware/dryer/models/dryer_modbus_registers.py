from dataclasses import dataclass
from enum import IntEnum
from typing import Mapping


class DryerModbusRegister(IntEnum):
    STATUS = 0
    COMMAND = 1

    PWM_OPEN_VRYTKA = 2
    PWM_CLOSE_VRYTKA = 3
    PWM_OPEN_IZBUTVATEL = 4
    PWM_CLOSE_IZBUTVATEL = 5

    TIME_DELAY_MOVE_SERVO_UP = 6
    TIME_DELAY_MOVE_SERVO_DOWN = 7
    TIME_DELAY_MOVE_SERVO_IN = 8
    TIME_DELAY_MOVE_SERVO_OUT = 9

    TIME_DELAY_MOVE_PLATE_IN = 10
    TIME_DELAY_MOVE_PLATE_OUT = 11

    TIME_DELAY_START_SERVO_MOVE = 12

    REV_MINUTE = 13
    ACCELERATION = 14

    TARGET_POSITION_BACKWORD = 15
    TARGET_POSITION_FORWORD = 16


@dataclass(frozen=True)
class DryerRegisterMap:
    """Runtime dryer addresses, defaulting to the firmware register map."""

    status: int = DryerModbusRegister.STATUS
    command: int = DryerModbusRegister.COMMAND
    pwm_open_vrytka: int = DryerModbusRegister.PWM_OPEN_VRYTKA
    pwm_close_vrytka: int = DryerModbusRegister.PWM_CLOSE_VRYTKA
    pwm_open_izbutvatel: int = DryerModbusRegister.PWM_OPEN_IZBUTVATEL
    pwm_close_izbutvatel: int = DryerModbusRegister.PWM_CLOSE_IZBUTVATEL
    time_delay_move_servo_up: int = DryerModbusRegister.TIME_DELAY_MOVE_SERVO_UP
    time_delay_move_servo_down: int = DryerModbusRegister.TIME_DELAY_MOVE_SERVO_DOWN
    time_delay_move_servo_in: int = DryerModbusRegister.TIME_DELAY_MOVE_SERVO_IN
    time_delay_move_servo_out: int = DryerModbusRegister.TIME_DELAY_MOVE_SERVO_OUT
    time_delay_move_plate_in: int = DryerModbusRegister.TIME_DELAY_MOVE_PLATE_IN
    time_delay_move_plate_out: int = DryerModbusRegister.TIME_DELAY_MOVE_PLATE_OUT
    time_delay_start_servo_move: int = DryerModbusRegister.TIME_DELAY_START_SERVO_MOVE
    rev_minute: int = DryerModbusRegister.REV_MINUTE
    acceleration: int = DryerModbusRegister.ACCELERATION
    target_position_backword: int = DryerModbusRegister.TARGET_POSITION_BACKWORD
    target_position_forword: int = DryerModbusRegister.TARGET_POSITION_FORWORD

    @classmethod
    def from_mapping(cls, addresses: Mapping[str, str | int]) -> "DryerRegisterMap":
        defaults = cls()
        return cls(**{
            name: int(addresses.get(name, getattr(defaults, name)))
            for name in cls.__dataclass_fields__
        })

    @property
    def addresses(self) -> tuple[int, ...]:
        return tuple(int(getattr(self, name)) for name in self.__dataclass_fields__)

    def require_contiguous(self) -> None:
        expected = tuple(range(self.status, self.status + len(self.addresses)))
        if self.addresses != expected:
            raise ValueError(
                "Dryer registers must be ordered and contiguous for FC16 writes: "
                f"got {self.addresses}, expected {expected}"
            )

@dataclass(frozen=True)
class DryerDefaults:
    status: int = 0                           # Register 0
    command: int = 0                          # Register 1

    pwm_open_vrytka: int = 150                # Register 2
    pwm_close_vrytka: int = 600               # Register 3
    pwm_open_izbutvatel: int = 600            # Register 4
    pwm_close_izbutvatel: int = 180           # Register 5

    time_delay_move_servo_up: int = 80         # Register 6
    time_delay_move_servo_down: int = 50       # Register 7
    time_delay_move_servo_in: int = 30         # Register 8
    time_delay_move_servo_out: int = 50        # Register 9

    time_delay_move_plate_in: int = 520        # Register 10
    time_delay_move_plate_out: int = 550       # Register 11

    time_delay_start_servo_move: int = 50      # Register 12

    rev_minute: int = 50                       # Register 13

    # Converted to integer tenths by DryerWriteData before the register write
    # (for example, a UI value of 0.1 is transmitted as 1).
    acceleration: float = 0.1                  # Register 14

    target_position_backword: int = 500        # Register 15
    target_position_forword: int = 500         # Register 16
