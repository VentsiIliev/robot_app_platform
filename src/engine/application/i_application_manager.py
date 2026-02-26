from abc import ABC, abstractmethod
from typing import Optional

from src.engine.application.application_state import ApplicationBusyState


class IApplicationManager(ABC):

    @property
    @abstractmethod
    def is_busy(self) -> bool: ...

    @property
    @abstractmethod
    def active_process_id(self) -> Optional[str]: ...

    @property
    @abstractmethod
    def state(self) -> ApplicationBusyState: ...

    @abstractmethod
    def acquire(self, process_id: str) -> bool: ...

    @abstractmethod
    def release(self, process_id: str) -> None: ...