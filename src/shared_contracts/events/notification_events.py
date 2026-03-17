from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class UserNotificationEvent:
    source: str
    severity: NotificationSeverity
    title_key: str = ""
    message_key: str = ""
    params: Mapping[str, object] = field(default_factory=dict)
    fallback_title: str = ""
    fallback_message: str = ""
    detail: str | None = None
    dedupe_key: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class NotificationTopics:
    USER = "ui/notification"
