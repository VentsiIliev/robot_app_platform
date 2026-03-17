from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class LanguageChangedEvent:
    language_code: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class LocalizationTopics:
    LANGUAGE_CHANGED = "localization/language_changed"
