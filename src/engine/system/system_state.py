from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SystemBusyState(Enum):
    IDLE = "idle"
    BUSY = "busy"


@dataclass(frozen=True)
class SystemStateEvent:
    state:          SystemBusyState
    active_process: Optional[str]
    message:        str      = ""
    timestamp:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SystemTopics:
    STATE = "system/state"