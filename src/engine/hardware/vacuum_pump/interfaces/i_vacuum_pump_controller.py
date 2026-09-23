from abc import ABC, abstractmethod


class IVacuumPumpController(ABC):
    @abstractmethod
    def turn_on(self) -> bool: ...

    @abstractmethod
    def turn_off(self) -> bool: ...

    def turn_off_nonblocking(self) -> bool:
        """Turn the pump off without waiting for an optional blow-off pulse.

        Controllers without asynchronous pulse support retain the safe,
        blocking behavior.
        """
        return self.turn_off()

    def read_state(self) -> bool:
        """Read the configured hardware output without changing it."""
        raise NotImplementedError

    def close(self) -> None:
        """Release any transport resources held by the controller."""
