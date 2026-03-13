from dataclasses import dataclass


@dataclass
class GlueDispensingConfig:
    use_segment_settings:          bool  = True
    turn_off_pump_between_paths:   bool  = True
    adjust_pump_speed_while_spray: bool  = True
    robot_tool:                    int   = 0
    robot_user:                    int   = 0
    global_velocity:               float = 10.0
    global_acceleration:           float = 30.0

