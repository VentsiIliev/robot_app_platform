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
        self._sequence_active = False
        self._last_sequence_succeeded = True
        self._last_error = ""
        self._completion = threading.Event()
        self._completion.set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def on_workpiece_release_verified(self) -> bool:
        """Queue next-position → eject processing and return immediately."""
        with self._lock:
            if self._stopped or self._sequence_active or not self._last_sequence_succeeded:
                return False
            self._sequence_active = True
            self._completion.clear()
            try:
                self._executor.submit(self._run_sequence)
            except RuntimeError:
                self._sequence_active = False
                self._last_sequence_succeeded = False
                self._last_error = "Failed to queue dryer sequence"
                self._completion.set()
                self._logger.exception("[DRYER_RELEASE] Failed to queue dryer sequence")
                return False
        self._logger.info("[DRYER_RELEASE] Queued next-position and eject sequence")
        return True

    def shutdown(self) -> None:
        with self._lock:
            self._stopped = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def wait_until_ready_for_release(self) -> tuple[bool, str]:
        """Wait for the previous sequence so another dropoff cannot overfill the dryer."""
        wait_s = (2.0 * self._status_timeout_s) + 1.0
        if not self._completion.wait(timeout=wait_s):
            reason = "the previous dryer sequence is still running"
            self._logger.error("[DRYER_RELEASE] Dropoff refused: %s", reason)
            return False, reason
        with self._lock:
            ready = not self._sequence_active and self._last_sequence_succeeded
            reason = self._last_error
        if ready:
            return True, ""
        reason = reason or "the previous dryer sequence failed"
        self._logger.error("[DRYER_RELEASE] Dropoff refused: %s", reason)
        return False, reason

    def _run_sequence(self) -> None:
        succeeded = False
        error = "Dryer sequence did not complete"
        try:
            initial_state = self._dryer.get_state()
            if not bool(self._dryer.next_position()):
                error = "NEXT_POSITION command failed"
                self._logger.error("[DRYER_RELEASE] NEXT_POSITION command failed")
                return
            if not self._wait_for_next_position_cycle(initial_state):
                error = "NEXT_POSITION completion was not confirmed"
                return
            eject_initial_state = self._dryer.get_state()
            if not bool(self._dryer.eject()):
                error = "EJECT command failed"
                self._logger.error("[DRYER_RELEASE] EJECT command failed")
                return
            if not self._wait_for_eject_cycle(eject_initial_state):
                error = "EJECT completion was not confirmed"
                return
            succeeded = True
            error = ""
        except Exception:
            error = "Dryer sequence raised an exception"
            self._logger.exception("[DRYER_RELEASE] Dryer sequence raised")
        finally:
            with self._lock:
                self._sequence_active = False
                self._last_sequence_succeeded = succeeded
                self._last_error = error
                self._completion.set()

    def _wait_for_next_position_cycle(self, initial_state: object) -> bool:
        """Require a fresh move transition before accepting NEXT_POSITION_DONE."""
        initial_healthy = bool(getattr(initial_state, "is_healthy", False))
        initial_done = bool(getattr(initial_state, "next_position_done", False))
        movement_observed = initial_healthy and not initial_done
        deadline = time.monotonic() + self._status_timeout_s
        while True:
            with self._lock:
                if self._stopped:
                    return False
            state = self._dryer.get_state()
            healthy = bool(getattr(state, "is_healthy", False))
            moving = bool(getattr(state, "next_position_moving", False))
            done = bool(getattr(state, "next_position_done", False))
            if healthy and (moving or not done):
                movement_observed = True
            if healthy and movement_observed and done and not moving:
                self._logger.info("[DRYER_RELEASE] NEXT_POSITION completed after fresh movement transition")
                return True
            if time.monotonic() >= deadline:
                self._logger.error(
                    "[DRYER_RELEASE] NEXT_POSITION fresh status cycle was not confirmed within %.1f s",
                    self._status_timeout_s,
                )
                return False
            time.sleep(self._status_poll_interval_s)

    def _wait_for_eject_cycle(self, initial_state: object) -> bool:
        """Accept a fresh EJECT_DONE edge or an eject-active-to-ready cycle."""
        initial_done = bool(getattr(initial_state, "eject_done", False))
        activity_observed = bool(getattr(initial_state, "ejecting", False))
        last_raw = None
        deadline = time.monotonic() + self._status_timeout_s
        while True:
            with self._lock:
                if self._stopped:
                    return False
            state = self._dryer.get_state()
            healthy = bool(getattr(state, "is_healthy", False))
            ready = bool(getattr(state, "is_ready", True))
            ejecting = bool(getattr(state, "ejecting", False))
            done = bool(getattr(state, "eject_done", False))
            raw = int(getattr(state, "raw_status", 0) or 0)
            if raw != last_raw:
                self._logger.info(
                    "[DRYER_RELEASE] EJECT status raw=%#06x healthy=%s ready=%s ejecting=%s eject_done=%s",
                    raw, healthy, ready, ejecting, done,
                )
                last_raw = raw
            if healthy and (ejecting or not ready or (done and not initial_done)):
                activity_observed = True
            if healthy and activity_observed and not ejecting and (done or ready):
                completion = "EJECT_DONE" if done else "return-to-ready"
                self._logger.info("[DRYER_RELEASE] EJECT completed via %s", completion)
                return True
            if time.monotonic() >= deadline:
                self._logger.error(
                    "[DRYER_RELEASE] EJECT fresh status cycle was not confirmed within %.1f s",
                    self._status_timeout_s,
                )
                return False
            time.sleep(self._status_poll_interval_s)
