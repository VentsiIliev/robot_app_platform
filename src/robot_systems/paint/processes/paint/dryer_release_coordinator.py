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
        eject_confirmation_delay_s: float = 1.0,
        next_position_confirmation_delay_s: float = 0.3,
    ) -> None:
        self._dryer = dryer
        self._status_timeout_s = max(0.0, float(status_timeout_s))
        self._status_poll_interval_s = max(0.0, float(status_poll_interval_s))
        self._eject_confirmation_delay_s = max(0.0, float(eject_confirmation_delay_s))
        self._next_position_confirmation_delay_s = max(
            0.0, float(next_position_confirmation_delay_s)
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="PaintDryerRelease")
        self._lock = threading.Lock()
        self._stopped = False
        self._sequence_active = False
        self._sequence_ever_queued = False
        self._last_sequence_succeeded = True
        self._last_error = ""
        self._completion = threading.Event()
        self._completion.set()
        self._logger = logging.getLogger(self.__class__.__name__)

    def on_workpiece_release_verified(self) -> bool:
        """Queue next-position → eject processing and return immediately."""
        if not self._dryer_enabled():
            self._logger.info(
                "[DRYER_RELEASE] Dryer disabled; skipping NEXT_POSITION/EJECT sequence"
            )
            return True
        if not self._dryer_healthy():
            self._logger.error(
                "[DRYER_RELEASE] Dryer is enabled but not ready; refusing release sequence"
            )
            return False
        with self._lock:
            if self._stopped or self._sequence_active or not self._last_sequence_succeeded:
                return False
            self._sequence_active = True
            self._sequence_ever_queued = True
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
        if not self._dryer_enabled():
            self._logger.info("[DRYER_RELEASE] Dryer disabled; readiness check bypassed")
            return True, ""
        if not self._dryer_healthy():
            reason = str(
                getattr(self._dryer, "last_error", None)
                or "Dryer is enabled but not ready"
            )
            self._logger.error("[DRYER_RELEASE] Dropoff refused: %s", reason)
            return False, reason
        self._completion.wait()
        with self._lock:
            ready = not self._sequence_active and self._last_sequence_succeeded
            reason = self._last_error
            has_previous_sequence = self._sequence_ever_queued
        if not has_previous_sequence:
            return True, ""
        if ready:
            state = self._dryer.get_state()
            eject_done = bool(getattr(state, "eject_done", False))
            ejecting = bool(getattr(state, "ejecting", False))
            healthy = bool(getattr(state, "is_healthy", False))
            if healthy and eject_done and not ejecting:
                self._logger.info("[DRYER_RELEASE] Final EJECT_DONE check passed before dropoff")
                return True, ""
            reason = "EJECT_DONE was not confirmed before dropoff"
            self._logger.error(
                "[DRYER_RELEASE] Dropoff refused: final EJECT_DONE check failed "
                "healthy=%s ejecting=%s eject_done=%s",
                healthy, ejecting, eject_done,
            )
        reason = reason or "the previous dryer sequence failed"
        self._logger.error("[DRYER_RELEASE] Dropoff refused: %s", reason)
        return False, reason

    def _run_sequence(self) -> None:
        with self._lock:
            self._sequence_ever_queued = True
        succeeded = False
        error = "Dryer sequence did not complete"
        try:
            if not self._dryer_enabled():
                self._logger.info(
                    "[DRYER_RELEASE] Dryer disabled before worker execution; commands skipped"
                )
                succeeded = True
                error = ""
                return
            initial_state = self._dryer.get_state()
            self._logger.info(
                "[DRYER_RELEASE] Before NEXT_POSITION: state=%s",
                self._format_state(initial_state),
            )
            command_started = time.monotonic()
            command_result = self._dryer.next_position()
            self._logger.info(
                "[DRYER_RELEASE] NEXT_POSITION returned=%r elapsed_s=%.3f",
                command_result,
                time.monotonic() - command_started,
            )
            if not bool(command_result):
                error = "NEXT_POSITION command failed"
                self._logger.error("[DRYER_RELEASE] NEXT_POSITION command failed")
                return
            time.sleep(self._next_position_confirmation_delay_s)
            post_command_state = self._dryer.get_state()
            self._logger.info(
                "[DRYER_RELEASE] After NEXT_POSITION: state=%s",
                self._format_state(post_command_state),
            )
            if not self._wait_for_next_position_cycle(initial_state, post_command_state):
                error = "NEXT_POSITION completion was not confirmed"
                return
            eject_initial_state = self._dryer.get_state()
            if not bool(self._dryer.eject()):
                error = "EJECT command failed"
                self._logger.error("[DRYER_RELEASE] EJECT command failed")
                return
            if not self._confirm_eject_started(eject_initial_state):
                error = "EJECT start was not confirmed"
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

    def _dryer_enabled(self) -> bool:
        """Treat an explicit disabled state as simulation/bypass, never as failure."""
        if self._dryer is None:
            return False
        getter = getattr(self._dryer, "is_enabled", None)
        if not callable(getter):
            # Legacy/test implementations without enable control remain strict.
            return True
        try:
            return bool(getter())
        except Exception:
            self._logger.exception("[DRYER_RELEASE] Failed to read dryer enabled state")
            # Fail closed when an enabled-state provider exists but is unreadable.
            return True

    def _dryer_healthy(self) -> bool:
        """Fail closed while a managed dryer is initializing or unhealthy."""
        getter = getattr(self._dryer, "is_healthy", None)
        if not callable(getter):
            return True
        try:
            return bool(getter())
        except Exception:
            self._logger.exception("[DRYER_RELEASE] Failed to read dryer health state")
            return False

    def _wait_for_next_position_cycle(
        self,
        initial_state: object,
        first_state: object | None = None,
    ) -> bool:
        """Require a fresh move transition before accepting NEXT_POSITION_DONE."""
        movement_observed = False
        acknowledgement_deadline = time.monotonic() + self._status_timeout_s
        unhealthy_since: float | None = None
        states = ([first_state] if first_state is not None else [])
        while True:
            with self._lock:
                if self._stopped:
                    return False
            state = states.pop(0) if states else self._dryer.get_state()
            healthy = bool(getattr(state, "is_healthy", False))
            moving = bool(getattr(state, "next_position_moving", False))
            done = bool(getattr(state, "next_position_done", False))
            now = time.monotonic()
            if healthy and (moving or not done):
                movement_observed = True
            if healthy:
                unhealthy_since = None
            elif unhealthy_since is None:
                unhealthy_since = now
            if healthy and movement_observed and done and not moving:
                self._logger.info("[DRYER_RELEASE] NEXT_POSITION completed after fresh movement transition")
                return True
            if not movement_observed and now >= acknowledgement_deadline:
                self._logger.error(
                    "[DRYER_RELEASE] NEXT_POSITION movement was not acknowledged within %.1f s",
                    self._status_timeout_s,
                )
                return False
            if unhealthy_since is not None and now - unhealthy_since >= self._status_timeout_s:
                self._logger.error(
                    "[DRYER_RELEASE] NEXT_POSITION status remained unhealthy for %.1f s",
                    self._status_timeout_s,
                )
                return False
            time.sleep(self._status_poll_interval_s)

    def _confirm_eject_started(self, initial_state: object) -> bool:
        """Confirm the slow EJECT operation started with one delayed status read."""
        with self._lock:
            if self._stopped:
                return False
        time.sleep(self._eject_confirmation_delay_s)
        state = self._dryer.get_state()
        healthy = bool(getattr(state, "is_healthy", False))
        ejecting = bool(getattr(state, "ejecting", False))
        initial_ejecting = bool(getattr(initial_state, "ejecting", False))
        self._logger.info(
            "[DRYER_RELEASE] EJECT start check healthy=%s ejecting=%s previously_ejecting=%s",
            healthy, ejecting, initial_ejecting,
        )
        return healthy and ejecting

    @staticmethod
    def _format_state(state: object) -> str:
        if state is None:
            return "<none>"
        fields = (
            "is_healthy", "is_ready", "raw_status", "next_position_moving",
            "next_position_done", "ejecting", "eject_done", "communication_errors",
        )
        values = []
        for field in fields:
            if hasattr(state, field):
                values.append(f"{field}={getattr(state, field)!r}")
        return "{" + ", ".join(values) + "}" if values else repr(state)
