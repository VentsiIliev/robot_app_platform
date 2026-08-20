from abc import ABC, abstractmethod


class IFanControl(ABC):
    @abstractmethod
    def turn_on(self) -> None: ...

    @abstractmethod
    def turn_off(self) -> None: ...

    def read_state(self) -> bool:
        """Read the configured hardware output without changing it."""
        raise NotImplementedError
