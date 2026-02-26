from abc import ABC, abstractmethod

from src.engine.process.process_state import ProcessState
from src.engine.process.process_requirements import ProcessRequirements


class IProcess(ABC):
    """
    Lifecycle contract for any robot application process.

    State machine:
        IDLE    → start()          → RUNNING
        RUNNING → pause()          → PAUSED
        RUNNING → stop()           → STOPPED
        PAUSED  → start()/resume() → RUNNING
        PAUSED  → stop()           → STOPPED
        STOPPED → start()          → RUNNING   (restart)
        ERROR   → reset_errors()   → IDLE
        any     → set_error()      → ERROR
    """

    @property
    @abstractmethod
    def process_id(self) -> str: ...

    @property
    @abstractmethod
    def state(self) -> ProcessState: ...

    @property
    @abstractmethod
    def requirements(self) -> ProcessRequirements: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def resume(self) -> None: ...

    @abstractmethod
    def reset_errors(self) -> None: ...
