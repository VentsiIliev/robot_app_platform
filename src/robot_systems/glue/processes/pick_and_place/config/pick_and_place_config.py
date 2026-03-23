from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PlaneConfig:
    x_min:   float = -450.0
    x_max:   float =  350.0
    y_min:   float =  300.0
    y_max:   float =  700.0
    spacing: float =   30.0
    row_gap: float =   50.0


@dataclass
class MotionProfile:
    tool: int = 0
    user: int = 0
    velocity: float = 20.0
    acceleration: float = 10.0
    blend_radius: float = 0.0


@dataclass
class PickAndPlaceConfig:
    plane:                PlaneConfig        = field(default_factory=PlaneConfig)
    pick_motion:          MotionProfile      = field(default_factory=MotionProfile)
    place_motion:         MotionProfile      = field(default_factory=MotionProfile)
    z_safe:               float              = 350.0   # safe transit height mm
    descent_height_offset: float             = 150.0   # above z_safe for descent
    orientation_rx:       float              = 180.0
    orientation_ry:       float              = 0.0
    rz_orientation:       float              = 90.0
    pickup_target:        str                = "tool"  # camera_center | tool | gripper
    camera_to_tcp_x_offset: float            = 0.0
    camera_to_tcp_y_offset: float            = 0.0
    camera_to_tool_x_offset: float           = 0.0
    camera_to_tool_y_offset: float           = 0.0
    camera_center_x: float                   = 0.0
    camera_center_y: float                   = 0.0
    tool_point_x: float                      = 0.0
    tool_point_y: float                      = 0.0
    gripper_point_x: float                   = 0.0
    gripper_point_y: float                   = 0.0
    gripper_z_offsets:    Dict[int, float]   = field(default_factory=dict)  # gripper_id → z_offset
    max_vision_retries:   int                = 10
    vision_retry_delay_s: float              = 1.0
    height_adjustment_mm: float              = 2.0
    height_source:        str                = "zero"  # zero | measured | workpiece
