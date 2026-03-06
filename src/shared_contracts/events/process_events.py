from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List


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

@dataclass(frozen=True)
class ProcessBusyEvent:
    requested_by: str
    message:      str
    timestamp:    datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ServiceUnavailableEvent:
    process_id:       str
    missing_services: List[str]
    timestamp:        datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ProcessTopics:
    ACTIVE = "process/active/state"

    @staticmethod
    def state(process_id: str) -> str:
        return f"process/{process_id}/state"

    @staticmethod
    def error(process_id: str) -> str:
        return f"process/{process_id}/error"

    @staticmethod
    def service_unavailable(process_id: str) -> str:
        return f"process/{process_id}/service_unavailable"


    @staticmethod
    def busy(requester_id: str) -> str:
        return f"process/{requester_id}/busy"