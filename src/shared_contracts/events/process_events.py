from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ProcessState(Enum):
    IDLE    = "idle"
    RUNNING = "running"
    PAUSED  = "paused"
    STOPPED = "stopped"
    ERROR   = "error"


@dataclass(frozen=True)
class ProcessStateEvent:
    process_id: str
    state:      ProcessState
    previous:   ProcessState
    message:    str      = ""
    timestamp:  datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ProcessTopics:
    @staticmethod
    def state(process_id: str) -> str:
        return f"process/{process_id}/state"

    @staticmethod
    def error(process_id: str) -> str:
        return f"process/{process_id}/error"