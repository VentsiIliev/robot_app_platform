from abc import ABC, abstractmethod
from typing import Optional


class IGeneratorTimer(ABC):

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @property
    @abstractmethod
    def elapsed_seconds(self) -> Optional[float]: ...