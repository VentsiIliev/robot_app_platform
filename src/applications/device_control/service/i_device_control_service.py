from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class MotorEntry:
    name:    str
    address: int


class IDeviceControlService(ABC):

    @abstractmethod
    def get_motors(self) -> List[MotorEntry]: ...

    @abstractmethod
    def get_motor_health_snapshot(self) -> Dict[int, bool]:
        """Returns {address: is_healthy} for every configured motor.
        Does board I/O — call from a background thread."""
        ...

    @abstractmethod
    def laser_on(self) -> None: ...

    @abstractmethod
    def laser_off(self) -> None: ...

    @abstractmethod
    def vacuum_pump_on(self) -> bool: ...

    @abstractmethod
    def vacuum_pump_off(self) -> bool: ...

    @abstractmethod
    def motor_on(self, address: int) -> bool: ...

    @abstractmethod
    def motor_off(self, address: int) -> bool: ...

    @abstractmethod
    def generator_on(self) -> bool: ...

    @abstractmethod
    def generator_off(self) -> bool: ...

    @abstractmethod
    def is_laser_available(self) -> bool: ...

    @abstractmethod
    def is_vacuum_pump_available(self) -> bool: ...

    @abstractmethod
    def is_motor_available(self) -> bool: ...

    @abstractmethod
    def is_generator_available(self) -> bool: ...
