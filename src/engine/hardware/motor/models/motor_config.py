from dataclasses import dataclass, field
from typing import Dict


@dataclass
class MotorConfig:
    """
    Register map and timing constants for a motor controller board.
    Inject into MotorController — no hardcoded register addresses anywhere else.
    """
    slave_id:                        int   = 1
    health_check_trigger_register:   int   = 17
    motor_error_count_register:      int   = 20
    motor_error_registers_start:     int   = 21
    health_check_delay_s:            float = 3.0
    ramp_step_delay_s:               float = 0.001

    # Maps motor_address → error-code prefix digit
    # e.g. motor addr 0 → errors start with "1x" (11, 12, 13, 14)
    address_to_error_prefix: Dict[int, int] = field(
        default_factory=lambda: {0: 1, 2: 2, 4: 3, 6: 4}
    )