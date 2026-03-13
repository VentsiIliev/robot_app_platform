from dataclasses import dataclass
from typing import Optional


@dataclass
class VacuumPumpConfig:
    pump_register:         int            = 1
    on_value:              int            = 1
    off_value:             int            = 0
    blow_off_register:     Optional[int]  = None
    blow_off_on_value:     int            = 1
    blow_off_off_value:    int            = 0
    blow_off_pulse_seconds: float         = 0.3

