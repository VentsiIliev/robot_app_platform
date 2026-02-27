from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class MotorState:
    motor_address:        int
    is_healthy:           bool      = False
    error_codes:          List[int] = field(default_factory=list)
    communication_errors: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.error_codes or self.communication_errors)

    def describe_errors(self) -> List[str]:
        """Returns raw error codes as strings — decoder is in the transport layer."""
        return [f"error code {c}" for c in self.error_codes] + self.communication_errors

    def __str__(self) -> str:
        return (
            f"Motor {self.motor_address}: "
            f"healthy={self.is_healthy}, "
            f"errors={self.error_codes}, "
            f"comm_errors={self.communication_errors}"
        )


@dataclass
class MotorsSnapshot:
    success: bool
    motors:  Dict[int, MotorState] = field(default_factory=dict)

    def get_motor(self, address: int) -> Optional[MotorState]:
        return self.motors.get(address)

    def add(self, state: MotorState) -> None:
        self.motors[state.motor_address] = state

    def all_healthy(self) -> bool:
        return self.success and all(m.is_healthy for m in self.motors.values())

    def get_all_errors_sorted(self) -> List[Tuple[int, int]]:
        pairs = [
            (code, state.motor_address)
            for state in self.motors.values()
            for code in state.error_codes
        ]
        return sorted(pairs)
