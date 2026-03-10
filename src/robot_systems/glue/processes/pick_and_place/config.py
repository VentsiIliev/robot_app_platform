from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PlaneConfig:
    x_min:   float = -450.0
    x_max:   float =  350.0
    y_min:   float =  300.0
    y_max:   float =  700.0
    spacing: float =   30.0


@dataclass
class PickAndPlaceConfig:
    plane:                PlaneConfig        = field(default_factory=PlaneConfig)
    z_safe:               float              = 350.0   # safe transit height mm
    descent_height_offset: float             = 150.0   # above z_safe for descent
    rz_orientation:       float              = 90.0
    gripper_x_offset:     float              = 100.429
    gripper_y_offset:     float              =   1.991
    gripper_z_offsets:    Dict[int, float]   = field(default_factory=dict)  # gripper_id → z_offset
    max_vision_retries:   int                = 10
    vision_retry_delay_s: float              = 1.0
    height_adjustment_mm: float              = 2.0