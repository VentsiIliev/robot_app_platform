from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class PaintExecutionControl:
    """Cooperative pause/resume state for a single paint execution run."""

    def __init__(self) -> None:
        self._pause_requested = threading.Event()
        self._resume_allowed = threading.Event()
        self._stop_requested = threading.Event()
        self._lock = threading.Lock()
        self._protected_phase_depth = 0
        self._resume_allowed.set()

    def request_pause(self) -> None:
        self._pause_requested.set()
        self._resume_allowed.clear()

    def resume(self) -> None:
        self._pause_requested.clear()
        self._resume_allowed.set()

    def request_stop(self) -> None:
        self._stop_requested.set()
        self._resume_allowed.set()

    def reset(self) -> None:
        self._pause_requested.clear()
        self._stop_requested.clear()
        self._resume_allowed.set()
        with self._lock:
            self._protected_phase_depth = 0

    def should_stop(self) -> bool:
        return self._stop_requested.is_set()

    def pause_requested(self) -> bool:
        return self._pause_requested.is_set()

    def in_protected_phase(self) -> bool:
        with self._lock:
            return self._protected_phase_depth > 0

    def wait_if_paused(self) -> bool:
        if not self._pause_requested.is_set():
            return not self.should_stop()
        while self._pause_requested.is_set() and not self.should_stop():
            self._resume_allowed.wait(timeout=0.05)
        return not self.should_stop()

    @contextmanager
    def protected_phase(self) -> Iterator[None]:
        with self._lock:
            self._protected_phase_depth += 1
        try:
            yield
        finally:
            with self._lock:
                self._protected_phase_depth -= 1
