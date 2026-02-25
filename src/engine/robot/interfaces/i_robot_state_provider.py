from abc import ABC, abstractmethod
from typing import List


class IRobotStateProvider(ABC):

    @property
    @abstractmethod
    def position(self) -> List[float]:
        ...

    @property
    @abstractmethod
    def velocity(self) -> float:
        ...

    @property
    @abstractmethod
    def acceleration(self) -> float:
        ...

    @property
    @abstractmethod
    def state(self) -> str:
        ...

    @property
    @abstractmethod
    def state_topic(self) -> str:
        ...

    @abstractmethod
    def start_monitoring(self) -> None:
        ...

    @abstractmethod
    def stop_monitoring(self) -> None:
        ...

