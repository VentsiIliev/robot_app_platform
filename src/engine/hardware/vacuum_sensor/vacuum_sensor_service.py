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

    # ── IVacuumSensorService ───────────────────────────────────────────

    def is_vacuum_detected(self) -> bool:
        for attempt in range(self._config.read_retries):
            try:
                read_input = getattr(self._transport, "read_input", None)
                raw = (
                    read_input(self._sensor_register)
                    if self._reads_input and read_input is not None
                    else self._transport.read_register(self._sensor_register)
                )
            except Exception:
                if attempt == self._config.read_retries - 1:
                    _logger.exception(
                        "Vacuum sensor read failed after %d attempts (register=%d)",
                        self._config.read_retries,
                        self._sensor_register,
                    )
                continue
            self._last_read_ok = True
            self._last_raw_value = int(raw)
            detected = raw == self._config.detected_value
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
        return False

    @property
    def last_raw_value(self) -> int | None:
        """Raw value returned by the most recent read, if any."""
        return self._last_raw_value

    # ── IHealthCheckable ───────────────────────────────────────────────

    def is_healthy(self) -> bool:
        """True when the last sensor read succeeded. No I/O."""
        return self._last_read_ok
