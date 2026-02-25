from abc import ABC, abstractmethod


class IRobotLifecycle(ABC):

    @abstractmethod
    def enable_robot(self) -> None:
        ...

    @abstractmethod
    def disable_robot(self) -> None:
        ...