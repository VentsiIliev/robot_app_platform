from __future__ import annotations

import logging
import time

from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_service import IVacuumSensorService
from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_transport import IVacuumSensorTransport
from src.engine.hardware.vacuum_sensor.models.vacuum_sensor_config import VacuumSensorConfig
from src.engine.hardware.xinje import XinjeMA8X8YR

_logger = logging.getLogger(__name__)
_SENSOR_LOG_INTERVAL_S = 1.0


class VacuumSensorService(IVacuumSensorService):
    """IVacuumSensorService implementation — reads a register via IVacuumSensorTransport.

    Answers one question: is_vacuum_detected(). A read failure is treated as
    "no vacuum" (fail-safe) and is reflected in the is_healthy() flag.
    """

    def __init__(
        self,
        transport: IVacuumSensorTransport,
        config:    VacuumSensorConfig,
    ) -> None:
        self._transport = transport
        self._config    = config
        point = config.sensor_register
        self._reads_input = isinstance(point, str) and point.strip().upper().startswith("X")
        self._sensor_register = (
            XinjeMA8X8YR.resolve_input(point)
            if self._reads_input
            else XinjeMA8X8YR.resolve_output(point)
        )
        self._last_read_ok = False
        self._last_raw_value: int | None = None
        self._last_logged_state: tuple[int, bool] | None = None
        self._last_log_at = 0.0
        self._read_sequence = 0
        self._total_read_calls = 0
        self._total_read_attempts = 0
        self._total_failed_attempts = 0
        self._total_failed_calls = 0
        self._last_read_diagnostics: dict[str, object] | None = None
        self._connect_transport()

    # ── IVacuumSensorService ───────────────────────────────────────────

    def is_vacuum_detected(self) -> bool:
        call_started_ns = time.monotonic_ns()
        attempt_durations_ms: list[float] = []
        failed_attempts = 0
        last_error: str | None = None
        for attempt in range(self._config.read_retries):
            attempt_started_ns = time.monotonic_ns()
            try:
                read_input = getattr(self._transport, "read_input", None)
                raw = (
                    read_input(self._sensor_register)
                    if self._reads_input and read_input is not None
                    else self._transport.read_register(self._sensor_register)
                )
            except Exception as exc:
                attempt_durations_ms.append(
                    (time.monotonic_ns() - attempt_started_ns) / 1_000_000.0
                )
                failed_attempts += 1
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt == self._config.read_retries - 1:
                    _logger.exception(
                        "Vacuum sensor read failed after %d attempts (register=%d)",
                        self._config.read_retries,
                        self._sensor_register,
                    )
                else:
                    self._reconnect_transport()
                continue
            attempt_durations_ms.append(
                (time.monotonic_ns() - attempt_started_ns) / 1_000_000.0
            )
            self._last_read_ok = True
            self._last_raw_value = int(raw)
            detected = raw == self._config.detected_value
            self._record_read_diagnostics(
                started_ns=call_started_ns,
                success=True,
                detected=detected,
                raw_value=int(raw),
                attempt_durations_ms=attempt_durations_ms,
                failed_attempts=failed_attempts,
                last_error=last_error,
            )
            state = (int(raw), detected)
            now = time.monotonic()
            if state != self._last_logged_state or now - self._last_log_at >= _SENSOR_LOG_INTERVAL_S:
                _logger.debug(
                    "Vacuum sensor register=%d raw=%d -> detected=%s",
                    self._sensor_register,
                    raw,
                    detected,
                )
                self._last_logged_state = state
                self._last_log_at = now
            return detected
        self._last_read_ok = False
        self._record_read_diagnostics(
            started_ns=call_started_ns,
            success=False,
            detected=False,
            raw_value=None,
            attempt_durations_ms=attempt_durations_ms,
            failed_attempts=failed_attempts,
            last_error=last_error,
        )
        return False

    def get_read_diagnostics(self) -> dict[str, object] | None:
        """Return a snapshot of measured sensor I/O, without performing I/O."""
        if self._last_read_diagnostics is None:
            return None
        snapshot = dict(self._last_read_diagnostics)
        snapshot["attempt_durations_ms"] = list(
            self._last_read_diagnostics["attempt_durations_ms"]
        )
        return snapshot

    def close(self) -> None:
        """Release the sensor's persistent transport connection."""
        self._transport.disconnect()

    def _connect_transport(self) -> None:
        self._transport.connect()
        _logger.info("Vacuum sensor persistent transport connection opened")

    def _reconnect_transport(self) -> None:
        self._transport.disconnect()
        self._connect_transport()

    def _record_read_diagnostics(
        self,
        *,
        started_ns: int,
        success: bool,
        detected: bool,
        raw_value: int | None,
        attempt_durations_ms: list[float],
        failed_attempts: int,
        last_error: str | None,
    ) -> None:
        finished_ns = time.monotonic_ns()
        attempts = len(attempt_durations_ms)
        self._read_sequence += 1
        self._total_read_calls += 1
        self._total_read_attempts += attempts
        self._total_failed_attempts += failed_attempts
        if not success:
            self._total_failed_calls += 1
        self._last_read_diagnostics = {
            "sequence": self._read_sequence,
            "started_monotonic_ns": started_ns,
            "finished_monotonic_ns": finished_ns,
            "duration_ms": (finished_ns - started_ns) / 1_000_000.0,
            "success": success,
            "detected": detected,
            "raw_value": raw_value,
            "attempts": attempts,
            "failed_attempts": failed_attempts,
            "attempt_durations_ms": list(attempt_durations_ms),
            "last_error": last_error,
            "total_read_calls": self._total_read_calls,
            "total_read_attempts": self._total_read_attempts,
            "total_failed_attempts": self._total_failed_attempts,
            "total_failed_calls": self._total_failed_calls,
        }

    @property
    def last_raw_value(self) -> int | None:
        """Raw value returned by the most recent read, if any."""
        return self._last_raw_value

    # ── IHealthCheckable ───────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """True when the last sensor read succeeded. No I/O."""
        return self._last_read_ok
