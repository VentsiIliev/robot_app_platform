from PyQt6.QtCore import QCoreApplication

from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from src.engine.robot.path_preparation import (
    PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR,
    PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL,
)
from src.robot_systems.paint.processes.paint.config import (
    MAGAZINE_PICKUP_MODES,
    PICKUP_CONTACT_MODES,
)

_CTX = "PaintProcessSettings"


def _t(text: str) -> str:
    translated = QCoreApplication.translate(_CTX, text)
    return translated or text


def _percent_field(
    key: str, label: str, default: float = 0.0, min_val: float = 0.0
) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "double_spinbox",
        default=default,
        min_val=min_val,
        max_val=100.0,
        step=1.0,
        decimals=1,
        suffix=" %",
        step_options=[1.0, 5.0, 10.0],
    )


def _mm_field(key: str, label: str, default: float = 0.0, min_val: float = -500.0) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "double_spinbox",
        default=default,
        min_val=min_val,
        max_val=1000.0,
        step=1.0,
        decimals=1,
        suffix=" mm",
        step_options=[0.5, 1.0, 5.0, 10.0],
    )


def _deg_field(key: str, label: str, default: float = 0.0, min_val: float = 0.0) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "double_spinbox",
        default=default,
        min_val=min_val,
        max_val=180.0,
        step=1.0,
        decimals=1,
        suffix=" deg",
        step_options=[0.5, 1.0, 5.0, 10.0],
    )


def _seconds_field(key: str, label: str, default: float = 0.0) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "double_spinbox",
        default=default,
        min_val=0.0,
        max_val=10.0,
        step=0.1,
        decimals=2,
        suffix=" s",
        step_options=[0.1, 0.5, 1.0],
    )


def _mm_per_second_field(key: str, label: str, default: float = 10.0) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "double_spinbox",
        default=default,
        min_val=0.0,
        max_val=500.0,
        step=1.0,
        decimals=1,
        suffix=" mm/s",
        step_options=[1.0, 5.0, 10.0, 25.0],
    )


def _toggle(key: str, label: str, default: bool = False) -> SettingField:
    return SettingField(key, _t(label), "toggle", default=default)


def _count_field(key: str, label: str, default: int = 1, max_val: int = 20) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "spinbox",
        default=int(default),
        min_val=1,
        max_val=max_val,
        step=1,
        step_options=[1, 2, 5],
    )


def _profile(key: str, label: str, vel: float, acc: float, motion_type: str = "ptp", blend_r: float = 0.0) -> dict:
    return {
        "key": key,
        "label": _t(label),
        "vel_percent": vel,
        "acc_percent": acc,
        "motion_type": motion_type,
        "blendR": blend_r,
    }


def _profile_table(key: str, label: str, rows: list[dict]) -> SettingField:
    return SettingField(key, _t(label), "paint_motion_profile_table", default=rows)


def build_process_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("General"), [
            _toggle("enable_vacuum_pump", "Enable Vacuum Pump"),
            _toggle("run_while_workpiece_found", "Run While Workpiece Found", True),
            _toggle("enable_workpiece_matching", "Enable Workpiece Matching", True),
            _toggle("enable_execution_state_timing", "Enable Execution State Timing", True),
            _toggle("pause_dashboard_live_view_after_capture", "Pause Dashboard Live View After Capture", True),
            _toggle("apply_camera_to_tcp_for_pickup", "Apply Camera-to-TCP Pickup Offset", True),
            _toggle("enable_z_shift_pixel_compensation", "Enable Z-Shift Pixel Compensation"),
        ]),
        SettingGroup(_t("Execution Mode"), [
            SettingField("pivot_motion_plane", _t("Paint Motion Plane"), "combo",
                         default="xz_y_ry", choices=["xz_y_ry", "xy_z_rz"]),
            SettingField("contour_pixel_to_mm_mode", _t("Pixel-to-mm Mode"), "combo",
                         default=PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR,
                         choices=[PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR, PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL]),
            SettingField("primary_group_id", _t("Primary Movement Group"), "line_edit", default="Vertical Shaft"),
            SettingField("secondary_group_id", _t("Secondary Movement Group"), "line_edit", default="Horizontal Shaft"),
            SettingField("cleanup_group_id", _t("Cleanup Movement Group"), "line_edit", default="Clean"),
        ]),
        SettingGroup(_t("Dropoff Strategy"), [
            SettingField("dropoff_strategy", _t("Strategy"), "combo",
                         default="pickup_origin", choices=["pickup_origin", "movement_group", "plate_layout"]),
            SettingField("dropoff_plate_bottom_left", _t("Plate Bottom-Left Pose"), "line_edit", default=""),
            SettingField("dropoff_plate_capture_bottom_left", _t("Capture Bottom-Left From Current Pose"), "paint_action_button", default=_t("Capture Bottom-Left From Current Pose")),
            SettingField("dropoff_plate_bottom_right", _t("Plate Bottom-Right Pose"), "line_edit", default=""),
            SettingField("dropoff_plate_capture_bottom_right", _t("Capture Bottom-Right From Current Pose"), "paint_action_button", default=_t("Capture Bottom-Right From Current Pose")),
            SettingField("dropoff_plate_top_right", _t("Plate Top-Right Pose"), "line_edit", default=""),
            SettingField("dropoff_plate_capture_top_right", _t("Capture Top-Right From Current Pose"), "paint_action_button", default=_t("Capture Top-Right From Current Pose")),
            SettingField("dropoff_plate_top_left", _t("Plate Top-Left Pose"), "line_edit", default=""),
            SettingField("dropoff_plate_capture_top_left", _t("Capture Top-Left From Current Pose"), "paint_action_button", default=_t("Capture Top-Left From Current Pose")),
            SettingField("dropoff_plate_robot_frame", _t("Captured Robot Frame"), "paint_pose_display", default=_t("Not captured")),
            _mm_field("dropoff_plate_release_z_offset_mm", "Plate Release Z Offset", 0.0),
            _mm_field("dropoff_plate_approach_clearance_mm", "Plate Approach Clearance", 50.0, min_val=0.0),
            _mm_field("dropoff_plate_margin_left_mm", "Plate Left Margin", 10.0, min_val=0.0),
            _mm_field("dropoff_plate_margin_right_mm", "Plate Right Margin", 10.0, min_val=0.0),
            _mm_field("dropoff_plate_margin_bottom_mm", "Plate Bottom Margin", 10.0, min_val=0.0),
            _mm_field("dropoff_plate_margin_top_mm", "Plate Top Margin", 10.0, min_val=0.0),
            _mm_field("dropoff_plate_spacing_x_mm", "Plate Horizontal Spacing", 10.0, min_val=0.0),
            _mm_field("dropoff_plate_spacing_y_mm", "Plate Vertical Spacing", 10.0, min_val=0.0),
            _toggle("dropoff_allow_sub_zero", "Allow Sub-Zero Dropoff"),
            _mm_field("dropoff_sub_zero_approach_z_mm", "Sub-Zero Approach/Retreat Z", 50.0, min_val=0.0),
            _mm_field("dropoff_corridor_x_margin_mm", "Sub-Zero Corridor X Margin (Dropoff X +/-)", 70.0, min_val=0.1),
            _mm_field("dropoff_corridor_y_margin_mm", "Sub-Zero Corridor Y Margin (Dropoff Y +/-)", 70.0, min_val=0.1),
            _mm_field("dropoff_corridor_z_tolerance_mm", "Sub-Zero Corridor Z Tolerance Below Dropoff", 1.0, min_val=0.0),
            _mm_field("dropoff_corridor_entry_z_max_mm", "Sub-Zero Corridor Entry Z Maximum", 100.0, min_val=0.0),
            _percent_field("dropoff_corridor_maximum_velocity_percent", "Sub-Zero Corridor Maximum Velocity", 80.0, min_val=0.1),
            _percent_field("dropoff_corridor_maximum_acceleration_percent", "Sub-Zero Corridor Maximum Acceleration", 60.0, min_val=0.1),
        ]),
        SettingGroup(_t("Magazine Load"), [
            _toggle("magazine_load_enabled", "Load From Magazine Before Paint"),
            SettingField(
                "magazine_pickup_mode",
                _t("Magazine Pickup Mode"),
                "combo",
                default="vision_planned",
                choices=list(MAGAZINE_PICKUP_MODES),
            ),
            SettingField(
                "magazine_fixed_pickup_group_id",
                _t("Fixed Pickup Movement Group"),
                "line_edit",
                default="Magazine Fixed Pickup",
            ),
            _mm_field(
                "magazine_fixed_pickup_position_tolerance_mm",
                "Fixed Pickup Position Tolerance",
                2.0,
                min_val=0.0,
            ),
            SettingField(
                "magazine_fixed_pickup_orientation_tolerance_deg",
                _t("Fixed Pickup Orientation Tolerance"),
                "double_spinbox",
                default=1.0,
                min_val=0.0,
                max_val=180.0,
                step=0.1,
                decimals=1,
                suffix=" deg",
                step_options=[0.1, 0.5, 1.0],
            ),
            _mm_field("magazine_release_z_mm", "Release Z", 50.0, min_val=0.0),
            _toggle("magazine_full_retract_before_release", "Full Retract Before Release", True),
            _mm_field("magazine_short_retract_distance_mm", "Short Retract Distance", 10.0, min_val=1.0),
            _seconds_field("magazine_camera_settle_s", "Camera Settle After Magazine Move", 0.5),
            _seconds_field("magazine_release_settle_s", "Settle After Calibration Release", 0.5),
        ]),
        SettingGroup(_t("Calibration Pickup"), [
            SettingField(
                "pickup_contact_mode",
                _t("Calibration Pickup Mode"),
                "combo",
                default="planned",
                choices=list(PICKUP_CONTACT_MODES),
            ),
        ]),
        SettingGroup(_t("Sensor-Controlled Fast LIN"), [
            _mm_field("pickup_servo_contact_min_z_mm", "Descent Target / Minimum Z", 0.0, min_val=-100.0),
            _percent_field("pickup_servo_contact_fast_lin_velocity_percent", "Descent Velocity", 10.0),
            _percent_field("pickup_servo_contact_fast_lin_acceleration_percent", "Descent Acceleration", 30.0),
            _seconds_field("pickup_servo_contact_timeout_s", "Detection Timeout", 5.0),
            _seconds_field("pickup_servo_contact_poll_interval_s", "Sensor Poll Interval", 0.02),
            _count_field("pickup_servo_contact_preflight_read_attempts", "Preflight Read Attempts", 2),
            _count_field("pickup_servo_contact_read_failure_limit", "Active Read Failure Limit", 3),
            _toggle("pickup_servo_contact_fallback_to_planned_descend", "Fallback To Planned Descend"),
            _toggle("pickup_servo_contact_dummy_sensor_enabled", "Use Dummy Pickup Sensor (TEST ONLY)"),
            _seconds_field("pickup_servo_contact_dummy_detect_after_s", "Dummy Detect After", 1.0),
        ]),
        SettingGroup(_t("Safe Travel"), [
            _toggle("safe_travel_enabled", "Use Waypoint Between Calibration and Paint"),
            SettingField(
                "safe_travel_positions",
                _t("Calibration to Paint Waypoints"),
                "paint_waypoint_table",
                default={"vel_percent": 50.0, "acc_percent": 20.0},
            ),
            _toggle("dropoff_safe_travel_enabled", "Use Waypoint Between Paint and Dropoff"),
            SettingField(
                "dropoff_safe_travel_positions",
                _t("Paint to Dropoff Waypoints"),
                "paint_waypoint_table",
                default={"vel_percent": 60.0, "acc_percent": 40.0},
            ),
        ]),
    ]


def build_motion_speed_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Paint Contact"), [
            _percent_field("staging_attach_vel_percent", "Attach Velocity", 10.0),
            _percent_field("staging_attach_acc_percent", "Attach Acceleration", 5.0),
        ]),
        SettingGroup(_t("Unmatched Workpiece Painting"), [
            _percent_field(
                "default_paint_velocity_percent",
                "Default Paint Velocity",
                10.0,
            ),
            _percent_field(
                "default_paint_acceleration_percent",
                "Default Paint Acceleration",
                10.0,
            ),
            _mm_field(
                "default_paint_offset_mm",
                "Default Paint Offset",
            ),
        ]),
        SettingGroup(_t("Pickup"), [
            _profile_table("pickup_motion_profiles", "Pickup Motion Profiles", [
                _profile("approach", "Approach", 60.0, 50.0, "ptp", 20.0),
                _profile("descend", "Descend", 60.0, 40.0, "linear", 0.0),
                _profile("lift_align", "Lift/Align", 80.0, 40.0, "ptp", 20.0),
                _profile("change_plane", "Change Plane", 80.0, 40.0, "ptp", 20.0),
                _profile("stage_transition", "Stage Transition", 50.0, 20.0, "ptp", 20.0),
                _profile("first_contact", "First Contact", 80.0, 30.0, "ptp", 0.0),
            ]),
        ]),
        SettingGroup(_t("Magazine Load"), [
            _profile_table("magazine_motion_profiles", "Magazine Motion Profiles", [
                _profile("move_to_magazine", "Move to Magazine", 30.0, 30.0, "ptp", 0.0),
                _profile("transfer_to_calibration", "Magazine to Calibration", 30.0, 30.0, "ptp", 0.0),
            ]),
        ]),
        SettingGroup(_t("Cleanup"), [
            _profile_table("cleanup_motion_profiles", "Cleanup Motion Profiles", [
                _profile("cleanup", "Cleanup", 80.0, 60.0, "linear", 0.0),
            ]),
        ]),
        SettingGroup(_t("Dropoff"), [
            _profile_table("dropoff_motion_profiles", "Dropoff Motion Profiles", [
                _profile("release_align", "Release Align", 60.0, 40.0, "ptp", 0.0),
            ]),
        ]),
        SettingGroup(_t("Navigation"), [
            _percent_field("nav_unwind_vel_percent", "Joint 6 Unwind Velocity"),
            _percent_field("nav_unwind_acc_percent", "Joint 6 Unwind Acceleration"),
            _profile_table("navigation_motion_profiles", "Navigation Motion Profiles", [
                _profile("calibration_move", "Move to Calibration", 30.0, 40.0, "ptp", 0.0),
            ]),
        ]),
    ]


def build_distance_offset_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Pickup Heights"), [
            _mm_field("pickup_approach_offset_mm", "Approach Offset", min_val=0.0),
            _mm_field("pickup_contact_offset_mm", "Contact Offset", min_val=0.0),
            _mm_field("pickup_initial_lift_clearance_mm", "Initial Lift Clearance", min_val=0.0),
        ]),
        SettingGroup(_t("Paint Contact Attach Offsets"), [
            _mm_field("staging_attach_z_offset_mm", "Attach Robot Z Offset"),
            _mm_field("staging_attach_paint_axis_offset_mm", "Attach Paint-Axis Offset"),
            _mm_field(
                "staging_attach_perpendicular_axis_offset_mm",
                "Attach Perpendicular-Axis Offset",
            ),
        ]),
        SettingGroup(_t("Paint Contact Detach Offsets"), [
            _mm_field("staging_detach_z_offset_mm", "Detach Robot Z Offset"),
            _mm_field("staging_detach_paint_axis_offset_mm", "Detach Paint-Axis Offset"),
            _mm_field(
                "staging_detach_perpendicular_axis_offset_mm",
                "Detach Perpendicular-Axis Offset",
            ),
        ]),
        SettingGroup(_t("Cleanup Offsets"), [
            _mm_field("cleanup_z_offset_mm", "Cleanup Z Offset"),
            _mm_field(
                "cleanup_perpendicular_retreat_offset_mm",
                "Perpendicular-Axis Approach/Retreat Offset",
            ),
            _mm_field("cleanup_second_pass_pivot_z_offset_mm", "Second-Pass Pivot Z Offset"),
        ]),
    ]


def build_paint_path_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Closed Contour"), [
            _mm_field("closed_contour_overlap_mm", "Paint Overlap", default=0.0, min_val=0.0),
        ]),
        SettingGroup(_t("Pivot Setup"), [
            SettingField("pivot_axis", _t("Pivot Axis"), "combo", default="x", choices=["x", "y", "z"]),
            SettingField("pivot_direction", _t("Pivot Direction"), "combo",
                         default="reverse", choices=["forward", "reverse"]),
            SettingField("pivot_contact_side", _t("Pivot Contact Side"), "combo",
                         default="positive", choices=["positive", "negative"]),
            SettingField("pickup_axis_alignment_sign_value", _t("Pickup Axis Alignment Sign"), "combo",
                         default="1.0", choices=["1.0", "-1.0"]),
            _toggle("mirror_xz_ry_execution_rotation_value", "Mirror XZ/RY Execution Rotation", True),
            _toggle("combine_change_plane_with_first_contact", "Combine Plane Change With First Contact", True),
        ]),
    ]


def build_cleanup_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Enable"), [
            _toggle("cleanup_enabled_after_xz_ry", "Enable Cleanup After XZ/RY Paint"),
            _toggle("cleanup_enabled_after_xy_rz", "Enable Cleanup After XY/RZ Paint"),
            _toggle("cleanup_enable_second_pass", "Enable Second Cleanup Pass"),
        ]),
        SettingGroup(_t("Path"), [
            _mm_field("cleanup_spacing_mm", "Cleanup Spacing", min_val=0.1),
        ]),
    ]


def build_interpolation_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Path Tangent"), [
            _mm_field("path_tangent_lookahead_mm", "Tangent Lookahead", default=15.0, min_val=1.0),
            _deg_field("path_tangent_deadband_deg", "Tangent Deadband", default=5.0, min_val=0.0),
        ]),
    ]


def build_diagnostics_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Debug"), [
            _toggle("enable_path_debug_plots", "Enable Path Debug Plots"),
            _toggle("enable_pivot_debug_plot", "Enable Pivot Debug Plot"),
            _toggle("enable_execution_motion_trace", "Enable Execution Motion Trace"),
            SettingField("execution_motion_trace_sample_period_s", _t("Motion Trace Sample Period"), "double_spinbox",
                         default=0.05, min_val=0.01, max_val=5.0, step=0.01, decimals=2, suffix=" s",
                         step_options=[0.01, 0.05, 0.1, 0.5]),
            _toggle("nav_unwind_queue_if_busy", "Queue Joint 6 Unwind If Busy", True),
        ]),
    ]


def build_paint_process_settings_tabs() -> list[tuple[str, list[SettingGroup]]]:
    return [
        (_t("Process"), build_process_groups()),
        (_t("Motion Speeds"), build_motion_speed_groups()),
        (_t("Distances & Offsets"), build_distance_offset_groups()),
        (_t("Paint Path"), build_paint_path_groups()),
        (_t("Interpolation"), build_interpolation_groups()),
        (_t("Cleanup"), build_cleanup_groups()),
        (_t("Diagnostics"), build_diagnostics_groups()),
    ]
