from __future__ import annotations

import logging

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
        self.simulated_value = simulated_value
        self.raise_on_read: bool = False
        self.call_log: List[tuple] = []

    def read_register(self, address: int) -> int:
        self.call_log.append(("read_register", address, self.simulated_value))
        if self.raise_on_read:
            _logger.info("[DUMMY VACUUM SENSOR] read_register(addr=%d) -> RAISED", address)
            raise IOError("Simulated vacuum-sensor read failure")
        _logger.info(
            "[DUMMY VACUUM SENSOR] read_register(addr=%d) -> %d",
            address,
            self.simulated_value,
        )
        return self.simulated_value
