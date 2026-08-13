from __future__ import annotations

from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_service import (
    IVacuumSensorService,
)


class VacuumPickupCondition:
    """Adapter from IVacuumSensorService to the generic pickup condition shape."""

    def __init__(self, vacuum_sensor: IVacuumSensorService) -> None:
        self._vacuum_sensor = vacuum_sensor

    def is_active(self) -> bool:
        return bool(self._vacuum_sensor.is_vacuum_detected())
