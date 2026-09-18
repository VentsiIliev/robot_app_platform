from __future__ import annotations

from src.engine.hardware.vacuum_sensor.interfaces.i_vacuum_sensor_service import (
    IVacuumSensorService,
)


class VacuumPickupCondition:
    """Adapter from IVacuumSensorService to the generic pickup condition shape."""

    def __init__(self, vacuum_sensor: IVacuumSensorService) -> None:
        self._vacuum_sensor = vacuum_sensor

    def is_active(self) -> bool:
        detected = bool(self._vacuum_sensor.is_vacuum_detected())
        if not self._vacuum_sensor.is_healthy():
            raise RuntimeError("Vacuum sensor read failed")
        return detected

    def get_read_diagnostics(self) -> dict[str, object] | None:
        """Expose cached transport timing when the concrete sensor supports it."""
        getter = getattr(self._vacuum_sensor, "get_read_diagnostics", None)
        return getter() if callable(getter) else None
