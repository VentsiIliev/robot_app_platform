from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List

from src.engine.hardware.motor.models.motor_state import MotorState, MotorsSnapshot


class IMotorController(ABC):
    """
    High-level motor command interface — communication-agnostic.
    Can be implemented over Modbus RTU, CAN bus, simulated drivers, etc.

    open()/close() provide a persistent connection lifetime for hot-path
    callers (e.g. continuous speed adjustment during glue dispensing).
    """

    def open(self) -> None:
        """Open a persistent connection. No-op if transport manages connections internally."""

    def close(self) -> None:
        """Close the persistent connection."""

    @abstractmethod
    def turn_on(
        self,
        motor_address:             int,
        speed:                     int,
        ramp_steps:                int,
        initial_ramp_speed:        int,
        initial_ramp_speed_duration: float,
    ) -> bool: ...

    @abstractmethod
    def turn_off(
        self,
        motor_address:   int,
        speed_reverse:   int,
        reverse_duration: float,
        ramp_steps:      int,
    ) -> bool: ...

    @abstractmethod
    def set_speed(self, motor_address: int, speed: int) -> bool:
        """Adjust speed without full start/stop sequence. Uses persistent connection if open."""

    @abstractmethod
    def health_check(self, motor_address: int) -> MotorState: ...

    @abstractmethod
    def health_check_all(self, motor_addresses: List[int]) -> MotorsSnapshot: ...