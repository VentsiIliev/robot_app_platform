from abc import ABC, abstractmethod
from typing import Optional

from src.engine.system import SystemBusyState


class ISystemManager(ABC):

    @property
    @abstractmethod
    def is_busy(self) -> bool: ...

    @property
    @abstractmethod
    def active_process_id(self) -> Optional[str]: ...

    @property
    @abstractmethod
    def state(self) -> SystemBusyState: ...

    @abstractmethod
    def acquire(self, process_id: str) -> bool: ...

    @abstractmethod
    def release(self, process_id: str) -> None: ...