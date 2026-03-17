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
    move_to_first_point_poll_s:    float = 0.02
    move_to_first_point_timeout_s: float = 30.0
    pump_thread_wait_poll_s:       float = 0.1
    final_position_poll_s:         float = 0.1
    pump_ready_timeout_s:          float = 5.0
    pump_thread_join_timeout_s:    float = 2.0
    pump_adjuster_poll_s:          float = 0.01
