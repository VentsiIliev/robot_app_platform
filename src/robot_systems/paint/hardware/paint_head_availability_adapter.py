from __future__ import annotations

from collections.abc import Callable, Mapping


class PaintHeadAvailabilityAdapter:
    """Devices-app toggle for the paint head; does not touch hardware."""

    key = "paint_head"
    label = "Paint Head"

    def __init__(
        self,
        enabled_provider: Callable[[], bool],
        persist_enabled: Callable[[str, bool], None],
    ) -> None:
        self._enabled_provider = enabled_provider
        self._persist_enabled = persist_enabled

    def actions(self) -> Mapping[str, str]:
        return {}

    def execute(self, action: str) -> bool:
        return False

    def read_state(self) -> Mapping[str, object]:
        return {"enabled": self.is_enabled(), "healthy": None, "error": ""}

    def set_enabled(self, enabled: bool) -> bool:
        self._persist_enabled(self.key, bool(enabled))
        return self.is_enabled() == bool(enabled)

    def is_enabled(self) -> bool:
        return bool(self._enabled_provider())

    def last_error(self) -> str | None:
        return None
