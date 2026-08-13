from __future__ import annotations

import logging
import threading

from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_transport import IVacuumSensorTransport

_logger = logging.getLogger(__name__)


class DummyVacuumSensorTransport(IVacuumSensorTransport):
    """Simulated vacuum-sensor transport for testing and manual simulation.

    Every read is logged so you can observe what the service asks for.
    Toggle `simulated_value` to simulate vacuum present (e.g. 1) or absent (0),
    and set `raise_on_read = True` to simulate a dead/failed sensor.

    - simulated_value: int  — the value returned by read_register().
    - raise_on_read:   bool — if True, every read raises IOError.
    - call_log:        list — ("read_register", address, value) per call.
    """

    def __init__(self, simulated_value: int = 0) -> None:
        self._lock = threading.Lock()
        self.simulated_value = int(simulated_value)
        self.raise_on_read: bool = False
        self.call_log: list[tuple] = []

    def read_register(self, address: int) -> int:
        with self._lock:
            value = int(self.simulated_value)
            raise_on_read = bool(self.raise_on_read)
            self.call_log.append(("read_register", address, value))

        if raise_on_read:
            _logger.info("[DUMMY VACUUM SENSOR] read_register(addr=%d) -> RAISED", address)
            raise IOError("Simulated vacuum-sensor read failure")
        _logger.info(
            "[DUMMY VACUUM SENSOR] read_register(addr=%d) -> %d",
            address,
            value,
        )
        return value

    def set_simulated_value(self, value: int) -> None:
        with self._lock:
            self.simulated_value = int(value)
        _logger.info("[DUMMY VACUUM SENSOR] simulated_value=%d", int(value))

    def set_vacuum_detected(
        self,
        detected: bool,
        *,
        detected_value: int = 1,
        clear_value: int = 0,
    ) -> None:
        self.set_simulated_value(detected_value if detected else clear_value)
