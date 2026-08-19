from abc import ABC, abstractmethod


class IVacuumPumpController(ABC):
    @abstractmethod
    def turn_on(self) -> bool: ...

    @abstractmethod
    def turn_off(self) -> bool: ...

    def close(self) -> None:
        """Release any transport resources held by the controller."""
