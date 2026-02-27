from __future__ import annotations
import logging
import threading
import time
from typing import Callable, Optional

from src.engine.hardware.generator.timer.i_generator_timer import IGeneratorTimer


class GeneratorTimer(IGeneratorTimer):

    def __init__(self, timeout_minutes: float, on_timeout: Callable[[], None], poll_interval_s: float = 5.0) -> None:
        self._timeout_s     = timeout_minutes * 60.0
        self._on_timeout    = on_timeout
        self._poll_interval = poll_interval_s
        self._start_time:   Optional[float] = None
        self._stop_time:    Optional[float] = None
        self._stop_event    = threading.Event()
        self._thread:       Optional[threading.Thread] = None
        self._logger        = logging.getLogger(self.__class__.__name__)

    def start(self) -> None:
        self._stop_event.clear()
        self._start_time = time.monotonic()
        self._stop_time  = None
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="GeneratorTimer")
        self._thread.start()
        self._logger.info("Timer started (timeout=%.1f min)", self._timeout_s / 60.0)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and threading.current_thread() is not self._thread:
            self._thread.join(timeout=2.0)
        self._stop_time = time.monotonic()
        self._logger.info("Timer stopped (elapsed=%.1fs)", self.elapsed_seconds or 0.0)

    @property
    def elapsed_seconds(self) -> Optional[float]:
        if self._start_time is None:
            return None
        end = self._stop_time if self._stop_time is not None else time.monotonic()
        return end - self._start_time

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if time.monotonic() - self._start_time >= self._timeout_s:
                self._logger.warning("Generator timeout reached")
                self._on_timeout()
                break
            self._stop_event.wait(timeout=self._poll_interval)


class NullGeneratorTimer(IGeneratorTimer):
    """No-op — use when timeout tracking is not needed."""

    def start(self) -> None: pass
    def stop(self)  -> None: pass

    @property
    def elapsed_seconds(self) -> Optional[float]:
        return None