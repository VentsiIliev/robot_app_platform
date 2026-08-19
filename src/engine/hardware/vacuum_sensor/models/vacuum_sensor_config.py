from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VacuumSensorConfig:
    """
    Register map and interpretation rules for a vacuum sensor.

    sensor_register — Modbus address or Xinje MA output label the sensor output sits on.
    detected_value  — raw register value that means "vacuum present".
                      Active-high sensor: 1. Active-low sensor: 0.
    read_retries    — how many read attempts before reporting failure.
    """

    sensor_register: int | str
    detected_value: int = 1
    read_retries: int = 3
