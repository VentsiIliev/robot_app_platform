from abc import abstractmethod

from src.engine.core.i_health_checkable import IHealthCheckable


class IVacuumSensorService(IHealthCheckable):
    """
    High-level vacuum-sensor interface — answers a single question:
    is vacuum currently detected?

    Communication-agnostic. Can be implemented over Modbus RTU,
    discrete I/O, simulated drivers, etc.
    """

    @abstractmethod
    def is_vacuum_detected(self) -> bool:
        """
        Return True when the sensor reports vacuum present.

        A read failure is treated as "no vacuum" (fail-safe). Implementations
        should update the health flag reported by is_healthy() on every read.
        """
