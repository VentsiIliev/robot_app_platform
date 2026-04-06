from copy import deepcopy

from src.engine.robot.configuration import RobotSettings, RobotCalibrationSettings


class RobotSettingsMapper:

    @staticmethod
    def to_flat_dict(settings: RobotSettings) -> dict:
        gm = settings.global_motion_settings
        sl = settings.safety_limits
        od = settings.offset_direction_map
        return {
            "robot_ip":            settings.robot_ip,
            "robot_tool":          settings.robot_tool,
            "robot_user":          settings.robot_user,
            "camera_to_tcp_x_offset":  settings.camera_to_tcp_x_offset,
            "camera_to_tcp_y_offset":  settings.camera_to_tcp_y_offset,
            "global_velocity":     gm.global_velocity,
            "global_acceleration": gm.global_acceleration,
            "emergency_decel":     gm.emergency_decel,
            "max_jog_step":        gm.max_jog_step,
            "tcp_x_step_distance": settings.tcp_x_step_distance,
            "tcp_x_step_offset":   settings.tcp_x_step_offset,
            "tcp_y_step_distance": settings.tcp_y_step_distance,
            "tcp_y_step_offset":   settings.tcp_y_step_offset,
            "offset_pos_x":        str(od.pos_x),
            "offset_neg_x":        str(od.neg_x),
            "offset_pos_y":        str(od.pos_y),
            "offset_neg_y":        str(od.neg_y),
            "safety_x_min":        sl.x_min,
            "safety_x_max":        sl.x_max,
            "safety_y_min":        sl.y_min,
            "safety_y_max":        sl.y_max,
            "safety_z_min":        sl.z_min,
            "safety_z_max":        sl.z_max,
            "safety_rx_min":       sl.rx_min,
            "safety_rx_max":       sl.rx_max,
            "safety_ry_min":       sl.ry_min,
            "safety_ry_max":       sl.ry_max,
            "safety_rz_min":       sl.rz_min,
            "safety_rz_max":       sl.rz_max,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: RobotSettings) -> RobotSettings:
        c  = deepcopy(base)
        gm = c.global_motion_settings
        sl = c.safety_limits
        od = c.offset_direction_map

        c.robot_ip            = flat.get("robot_ip",            c.robot_ip)
        c.robot_tool          = int(flat.get("robot_tool",      c.robot_tool))
        c.robot_user          = int(flat.get("robot_user",      c.robot_user))
        c.camera_to_tcp_x_offset = float(flat.get("camera_to_tcp_x_offset", c.camera_to_tcp_x_offset))
        c.camera_to_tcp_y_offset = float(flat.get("camera_to_tcp_y_offset", c.camera_to_tcp_y_offset))
        c.tcp_x_step_distance = float(flat.get("tcp_x_step_distance", c.tcp_x_step_distance))
        c.tcp_x_step_offset   = float(flat.get("tcp_x_step_offset",   c.tcp_x_step_offset))
        c.tcp_y_step_distance = float(flat.get("tcp_y_step_distance", c.tcp_y_step_distance))
        c.tcp_y_step_offset   = float(flat.get("tcp_y_step_offset",   c.tcp_y_step_offset))

        od.pos_x = flat.get("offset_pos_x", str(od.pos_x)) in ("True", "true", True)
        od.neg_x = flat.get("offset_neg_x", str(od.neg_x)) in ("True", "true", True)
        od.pos_y = flat.get("offset_pos_y", str(od.pos_y)) in ("True", "true", True)
        od.neg_y = flat.get("offset_neg_y", str(od.neg_y)) in ("True", "true", True)

        gm.global_velocity     = int(flat.get("global_velocity",     gm.global_velocity))
        gm.global_acceleration = int(flat.get("global_acceleration", gm.global_acceleration))
        gm.emergency_decel     = int(flat.get("emergency_decel",     gm.emergency_decel))
        gm.max_jog_step        = int(flat.get("max_jog_step",        gm.max_jog_step))

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
        ax = settings.axis_mapping
        tcp = settings.camera_tcp_offset
        return {
            "calib_min_step_mm":           am.min_step_mm,
            "calib_max_step_mm":           am.max_step_mm,
            "calib_target_error_mm":       am.target_error_mm,
            "calib_max_error_ref":         am.max_error_ref,
            "calib_k":                     am.k,
            "calib_derivative_scaling":    am.derivative_scaling,
            "calib_fast_iteration_wait":   am.fast_iteration_wait,
            "calib_initial_align_y_scale": am.initial_align_y_scale,
            "calib_run_height_measurement": settings.run_height_measurement,
            "calib_z_target":              settings.z_target,
            "calib_required_ids":          settings.required_ids,
            "calib_candidate_ids":         settings.candidate_ids,
            "calib_min_targets":           settings.min_targets,
            "calib_max_targets":           settings.max_targets,
            "calib_min_target_separation_px": settings.min_target_separation_px,
            "calib_velocity":              settings.velocity,
            "calib_acceleration":          settings.acceleration,
            "calib_axis_marker_id":        ax.marker_id,
            "calib_axis_move_mm":          ax.move_mm,
            "calib_axis_max_attempts":     ax.max_attempts,
            "calib_axis_delay_after_move": ax.delay_after_move_s,
            "calib_tcp_marker_id":         tcp.marker_id,
            "calib_tcp_run_during_main":   tcp.run_during_robot_calibration,
            "calib_tcp_max_markers":       tcp.max_markers_for_tcp_capture,
            "calib_tcp_rotation_step_deg": tcp.rotation_step_deg,
            "calib_tcp_iterations":        tcp.iterations,
            "calib_tcp_approach_z":        tcp.approach_z,
            "calib_tcp_approach_rx":       tcp.approach_rx,
            "calib_tcp_approach_ry":       tcp.approach_ry,
            "calib_tcp_approach_rz":       tcp.approach_rz,
            "calib_tcp_velocity":          tcp.velocity,
            "calib_tcp_acceleration":      tcp.acceleration,
            "calib_tcp_settle_time_s":     tcp.settle_time_s,
            "calib_tcp_detection_attempts": tcp.detection_attempts,
            "calib_tcp_retry_delay_s":     tcp.retry_delay_s,
            "calib_tcp_recenter_max_iterations": tcp.recenter_max_iterations,
            "calib_tcp_min_samples":       tcp.min_samples,
            "calib_tcp_max_acceptance_std_mm": tcp.max_acceptance_std_mm,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: RobotCalibrationSettings) -> RobotCalibrationSettings:
        s  = deepcopy(base)
        am = s.adaptive_movement
        ax = s.axis_mapping
        tcp = s.camera_tcp_offset

        am.min_step_mm        = float(flat.get("calib_min_step_mm",        am.min_step_mm))
        am.max_step_mm        = float(flat.get("calib_max_step_mm",        am.max_step_mm))
        am.target_error_mm    = float(flat.get("calib_target_error_mm",    am.target_error_mm))
        am.max_error_ref      = float(flat.get("calib_max_error_ref",      am.max_error_ref))
        am.k                  = float(flat.get("calib_k",                  am.k))
        am.derivative_scaling = float(flat.get("calib_derivative_scaling", am.derivative_scaling))
        am.fast_iteration_wait = float(flat.get("calib_fast_iteration_wait", am.fast_iteration_wait))
        am.initial_align_y_scale = float(
            flat.get("calib_initial_align_y_scale", am.initial_align_y_scale)
        )
        s.run_height_measurement = flat.get(
            "calib_run_height_measurement",
            s.run_height_measurement,
        ) in ("True", "true", True)
        s.z_target            = int(flat.get("calib_z_target",             s.z_target))
        s.required_ids        = flat.get("calib_required_ids",             s.required_ids)
        s.candidate_ids       = flat.get("calib_candidate_ids",            s.candidate_ids)
        s.min_targets         = int(flat.get("calib_min_targets",          s.min_targets))
        s.max_targets         = int(flat.get("calib_max_targets",          s.max_targets))
        s.min_target_separation_px = float(
            flat.get("calib_min_target_separation_px", s.min_target_separation_px)
        )
        s.velocity            = int(flat.get("calib_velocity",             s.velocity))
        s.acceleration        = int(flat.get("calib_acceleration",         s.acceleration))

        ax.marker_id          = int(flat.get("calib_axis_marker_id",        ax.marker_id))
        ax.move_mm            = float(flat.get("calib_axis_move_mm",        ax.move_mm))
        ax.max_attempts       = int(flat.get("calib_axis_max_attempts",     ax.max_attempts))
        ax.delay_after_move_s = float(flat.get("calib_axis_delay_after_move", ax.delay_after_move_s))

        tcp.marker_id         = int(flat.get("calib_tcp_marker_id",          tcp.marker_id))
        tcp.run_during_robot_calibration = flat.get(
            "calib_tcp_run_during_main",
            tcp.run_during_robot_calibration,
        ) in ("True", "true", True)
        tcp.max_markers_for_tcp_capture = int(flat.get("calib_tcp_max_markers", tcp.max_markers_for_tcp_capture))
        tcp.rotation_step_deg = float(flat.get("calib_tcp_rotation_step_deg", tcp.rotation_step_deg))
        tcp.iterations        = int(flat.get("calib_tcp_iterations",         tcp.iterations))
        tcp.approach_z        = float(flat.get("calib_tcp_approach_z",       tcp.approach_z))
        tcp.approach_rx       = float(flat.get("calib_tcp_approach_rx",      tcp.approach_rx))
        tcp.approach_ry       = float(flat.get("calib_tcp_approach_ry",      tcp.approach_ry))
        tcp.approach_rz       = float(flat.get("calib_tcp_approach_rz",      tcp.approach_rz))
        tcp.velocity          = int(flat.get("calib_tcp_velocity",           tcp.velocity))
        tcp.acceleration      = int(flat.get("calib_tcp_acceleration",       tcp.acceleration))
        tcp.settle_time_s     = float(flat.get("calib_tcp_settle_time_s",    tcp.settle_time_s))
        tcp.detection_attempts = int(flat.get("calib_tcp_detection_attempts", tcp.detection_attempts))
        tcp.retry_delay_s     = float(flat.get("calib_tcp_retry_delay_s",    tcp.retry_delay_s))
        tcp.recenter_max_iterations = int(flat.get("calib_tcp_recenter_max_iterations", tcp.recenter_max_iterations))
        tcp.min_samples       = int(flat.get("calib_tcp_min_samples",        tcp.min_samples))
        tcp.max_acceptance_std_mm = float(flat.get("calib_tcp_max_acceptance_std_mm", tcp.max_acceptance_std_mm))
        return s
