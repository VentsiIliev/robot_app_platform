from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class MotorConfig:
    """
    Register map, motor topology, and timing constants for a motor controller board.

    All register addresses are board firmware specific — no defaults are provided.
    Instantiate with explicit values in the robot vision_service that owns the hardware.

    motor_addresses         — ordered list of Modbus register addresses for each motor.
                              Length determines the motor count (1, 4, 44, …).
    address_to_error_prefix — optional mapping: motor_address → error-code prefix digit,
                              used to filter board-level error codes per motor.
                              Leave empty ({}) if the board does not use prefixed error codes.
    """

    # ── Register map (board firmware specific — no defaults) ──────────
    health_check_trigger_register: int
    motor_error_count_register:    int
    motor_error_registers_start:   int

    # ── Motor topology ────────────────────────────────────────────────
    motor_addresses: List[int]

    # ── Timing ───────────────────────────────────────────────────────
    health_check_delay_s: float = 0.0
    ramp_step_delay_s:    float = 0.001

    # ── Error code filtering (optional) ──────────────────────────────
    address_to_error_prefix: Dict[int, int] = field(default_factory=dict)