from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import logging
import threading
import time


class DryerReleaseCoordinator:
    """Run post-release dryer commands serially without blocking paint production."""

    def __init__(
        self,
        dryer,
        *,
        status_timeout_s: float = 10.0,
        status_poll_interval_s: float = 0.1,
    ) -> None:
        self._dryer = dryer
        self._status_timeout_s = max(0.0, float(status_timeout_s))
        self._status_poll_interval_s = max(0.0, float(status_poll_interval_s))
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="PaintDryerRelease")
        self._lock = threading.Lock()
        self._stopped = False
        self._logger = logging.getLogger(self.__class__.__name__)

    def on_workpiece_release_verified(self) -> bool:
        """Queue next-position → eject processing and return immediately."""
        with self._lock:
            if self._stopped:
                return False
            try:
                self._executor.submit(self._run_sequence)
            except RuntimeError:
                self._logger.exception("[DRYER_RELEASE] Failed to queue dryer sequence")
                return False
        self._logger.info("[DRYER_RELEASE] Queued next-position and eject sequence")
        return True

    def shutdown(self) -> None:
        with self._lock:
            self._stopped = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_sequence(self) -> None:
        try:
            if not bool(self._dryer.next_position()):
                self._logger.error("[DRYER_RELEASE] NEXT_POSITION command failed")
                return
            if not self._wait_for_status("next_position_done", "NEXT_POSITION"):
                return
            if not bool(self._dryer.eject()):
                self._logger.error("[DRYER_RELEASE] EJECT command failed")
                return
            self._wait_for_status("eject_done", "EJECT")
        except Exception:
            self._logger.exception("[DRYER_RELEASE] Dryer sequence raised")

    def _wait_for_status(self, attribute: str, label: str) -> bool:
        deadline = time.monotonic() + self._status_timeout_s
        while True:
            with self._lock:
                if self._stopped:
                    return False
            state = self._dryer.get_state()
            if bool(getattr(state, "is_healthy", False)) and bool(getattr(state, attribute, False)):
                self._logger.info("[DRYER_RELEASE] %s completed", label)
                return True
            if time.monotonic() >= deadline:
                self._logger.error(
                    "[DRYER_RELEASE] %s status was not confirmed within %.1f s",
                    label,
                    self._status_timeout_s,
                )
                return False
            time.sleep(self._status_poll_interval_s)
