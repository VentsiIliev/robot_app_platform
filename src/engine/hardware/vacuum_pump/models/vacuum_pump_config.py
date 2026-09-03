from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VacuumPumpConfig:
    pump_register: int | str = "Y0"
    on_value: int = 1
    off_value: int = 0
    blow_off_register: int | str | None = None
    blow_off_on_value: int = 1
    blow_off_off_value: int = 0
    blow_off_pulse_seconds: float = 0.0
