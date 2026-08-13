from __future__ import annotations

import logging
import time

_logger = logging.getLogger(__name__)


class TimedDummyPickupCondition:
    """Test-only pickup condition that becomes active after a delay."""

    def __init__(self, detect_after_s: float = 1.0) -> None:
        self._detect_after_s = max(0.0, float(detect_after_s))
        self._started_at: float | None = None

    def is_active(self) -> bool:
        if self._started_at is None:
            self._started_at = time.monotonic()
            _logger.warning(
                "[DUMMY_PICKUP_CONDITION] TEST ONLY dummy pickup condition armed detect_after_s=%.3f",
                self._detect_after_s,
            )
        return (time.monotonic() - self._started_at) >= self._detect_after_s
