from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class DispensingErrorKind(Enum):
    CONFIG = auto()
    MOTION = auto()
    PUMP = auto()
    GENERATOR = auto()
    THREAD = auto()
    STATE = auto()
    TIMEOUT = auto()


class DispensingErrorCode(Enum):
    MISSING_CURRENT_PATH = auto()
    MOVE_TO_FIRST_POINT_FAILED = auto()
    MOVE_TO_FIRST_POINT_TIMEOUT = auto()
    MOVE_LINEAR_FAILED = auto()
    EXECUTE_TRAJECTORY_FAILED = auto()
    INVALID_MOTOR_ADDRESS = auto()
    PUMP_ON_FAILED = auto()
    PUMP_OFF_FAILED = auto()
    GENERATOR_START_FAILED = auto()
    GENERATOR_STOP_FAILED = auto()
    PUMP_THREAD_START_FAILED = auto()
    PUMP_THREAD_READY_MISSING = auto()
    PUMP_THREAD_READY_TIMEOUT = auto()
    PUMP_THREAD_WAIT_FAILED = auto()
    PUMP_THREAD_EXECUTION_FAILED = auto()


@dataclass(slots=True)
class DispensingErrorInfo:
    kind: DispensingErrorKind
    code: DispensingErrorCode
    state: object
    operation: str
    message: str
    exception_type: str | None
    path_index: int
    point_index: int
    recoverable: bool = False
