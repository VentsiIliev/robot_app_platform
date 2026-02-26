from copy import deepcopy

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings


class RobotSettingsMapper:

    @staticmethod
    def to_flat_dict(config: RobotSettings) -> dict:
        return {
            "robot_ip":            config.robot_ip,
            "robot_tool":          config.robot_tool,
            "robot_user":          config.robot_user,
            "tcp_x_offset":        config.tcp_x_offset,
            "tcp_y_offset":        config.tcp_y_offset,
            "global_velocity":     config.global_motion_settings.global_velocity,
            "global_acceleration": config.global_motion_settings.global_acceleration,
            "emergency_decel":     config.global_motion_settings.emergency_decel,
            "max_jog_step":        config.global_motion_settings.max_jog_step,
            "tcp_x_step_distance": config.tcp_x_step_distance,
            "tcp_x_step_offset":   config.tcp_x_step_offset,
            "tcp_y_step_distance": config.tcp_y_step_distance,
            "tcp_y_step_offset":   config.tcp_y_step_offset,
            "offset_pos_x":        str(config.offset_direction_map.pos_x),
            "offset_neg_x":        str(config.offset_direction_map.neg_x),
            "offset_pos_y":        str(config.offset_direction_map.pos_y),
            "offset_neg_y":        str(config.offset_direction_map.neg_y),
            "safety_x_min":        config.safety_limits.x_min,
            "safety_x_max":        config.safety_limits.x_max,
            "safety_y_min":        config.safety_limits.y_min,
            "safety_y_max":        config.safety_limits.y_max,
            "safety_z_min":        config.safety_limits.z_min,
            "safety_z_max":        config.safety_limits.z_max,
            "safety_rx_min":       config.safety_limits.rx_min,
            "safety_rx_max":       config.safety_limits.rx_max,
            "safety_ry_min":       config.safety_limits.ry_min,
            "safety_ry_max":       config.safety_limits.ry_max,
            "safety_rz_min":       config.safety_limits.rz_min,
            "safety_rz_max":       config.safety_limits.rz_max,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: RobotSettings) -> RobotSettings:
        c = deepcopy(base)
        c.robot_ip            = flat.get("robot_ip",            c.robot_ip)
        c.robot_tool          = int(flat.get("robot_tool",          c.robot_tool))
        c.robot_user          = int(flat.get("robot_user",          c.robot_user))
        c.tcp_x_offset        = float(flat.get("tcp_x_offset",        c.tcp_x_offset))
        c.tcp_y_offset        = float(flat.get("tcp_y_offset",        c.tcp_y_offset))
        c.tcp_x_step_distance = float(flat.get("tcp_x_step_distance", c.tcp_x_step_distance))
        c.tcp_x_step_offset   = float(flat.get("tcp_x_step_offset",   c.tcp_x_step_offset))
        c.tcp_y_step_distance = float(flat.get("tcp_y_step_distance", c.tcp_y_step_distance))
        c.tcp_y_step_offset   = float(flat.get("tcp_y_step_offset",   c.tcp_y_step_offset))
        c.offset_direction_map.pos_x = flat.get("offset_pos_x", str(c.offset_direction_map.pos_x)) == "True"
        c.offset_direction_map.neg_x = flat.get("offset_neg_x", str(c.offset_direction_map.neg_x)) == "True"
        c.offset_direction_map.pos_y = flat.get("offset_pos_y", str(c.offset_direction_map.pos_y)) == "True"
        c.offset_direction_map.neg_y = flat.get("offset_neg_y", str(c.offset_direction_map.neg_y)) == "True"
        gm = c.global_motion_settings
        gm.global_velocity     = int(flat.get("global_velocity",     gm.global_velocity))
        gm.global_acceleration = int(flat.get("global_acceleration", gm.global_acceleration))
        gm.emergency_decel     = int(flat.get("emergency_decel",     gm.emergency_decel))
        gm.max_jog_step        = int(flat.get("max_jog_step",        gm.max_jog_step))
        sl = c.safety_limits
        sl.x_min  = int(flat.get("safety_x_min",  sl.x_min))
        sl.x_max  = int(flat.get("safety_x_max",  sl.x_max))
        sl.y_min  = int(flat.get("safety_y_min",  sl.y_min))
        sl.y_max  = int(flat.get("safety_y_max",  sl.y_max))
        sl.z_min  = int(flat.get("safety_z_min",  sl.z_min))
        sl.z_max  = int(flat.get("safety_z_max",  sl.z_max))
        sl.rx_min = int(flat.get("safety_rx_min", sl.rx_min))
        sl.rx_max = int(flat.get("safety_rx_max", sl.rx_max))
        sl.ry_min = int(flat.get("safety_ry_min", sl.ry_min))
        sl.ry_max = int(flat.get("safety_ry_max", sl.ry_max))
        sl.rz_min = int(flat.get("safety_rz_min", sl.rz_min))
        sl.rz_max = int(flat.get("safety_rz_max", sl.rz_max))
        return c


class RobotCalibrationMapper:

    @staticmethod
    def to_flat_dict(settings: RobotCalibrationSettings) -> dict:
        am = settings.adaptive_movement
        return {
            "calib_min_step_mm":        am.min_step_mm,
            "calib_max_step_mm":        am.max_step_mm,
            "calib_target_error_mm":    am.target_error_mm,
            "calib_max_error_ref":      am.max_error_ref,
            "calib_k":                  am.k,
            "calib_derivative_scaling": am.derivative_scaling,
            "calib_z_target":           settings.z_target,
            "calib_required_ids":       settings.required_ids,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: RobotCalibrationSettings) -> RobotCalibrationSettings:
        s = deepcopy(base)
        am = s.adaptive_movement
        am.min_step_mm        = float(flat.get("calib_min_step_mm",        am.min_step_mm))
        am.max_step_mm        = float(flat.get("calib_max_step_mm",        am.max_step_mm))
        am.target_error_mm    = float(flat.get("calib_target_error_mm",    am.target_error_mm))
        am.max_error_ref      = float(flat.get("calib_max_error_ref",      am.max_error_ref))
        am.k                  = float(flat.get("calib_k",                  am.k))
        am.derivative_scaling = float(flat.get("calib_derivative_scaling", am.derivative_scaling))
        s.z_target            = int(flat.get("calib_z_target",             s.z_target))
        s.required_ids        = flat.get("calib_required_ids",             s.required_ids)
        return s
