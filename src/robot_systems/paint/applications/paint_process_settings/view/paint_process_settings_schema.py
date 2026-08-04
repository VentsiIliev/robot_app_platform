from PyQt6.QtCore import QCoreApplication

from pl_gui.settings.settings_view.schema import SettingField, SettingGroup
from src.engine.robot.path_preparation import (
    PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR,
    PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL,
)

_CTX = "PaintProcessSettings"


def _t(text: str) -> str:
    translated = QCoreApplication.translate(_CTX, text)
    return translated or text


def _percent_field(key: str, label: str, default: float = 0.0) -> SettingField:
    return SettingField(
        key,
        _t(label),
        "double_spinbox",
        default=default,
        min_val=0.0,
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


def _toggle(key: str, label: str, default: bool = False) -> SettingField:
    return SettingField(key, _t(label), "toggle", default=default)


def build_process_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("General"), [
            _toggle("enable_vacuum_pump", "Enable Vacuum Pump"),
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
                         default="pickup_origin", choices=["pickup_origin", "movement_group"]),
        ]),
        SettingGroup(_t("Magazine Load"), [
            _toggle("magazine_load_enabled", "Load From Magazine Before Paint"),
            _seconds_field("magazine_camera_settle_s", "Camera Settle After Magazine Move", 0.5),
            _seconds_field("magazine_release_settle_s", "Settle After Calibration Release", 0.5),
        ]),
        SettingGroup(_t("Safe Travel"), [
            _toggle("safe_travel_enabled", "Use Waypoint Between Calibration and Paint"),
            SettingField(
                "safe_travel_position",
                _t("Calibration to Paint Pose"),
                "paint_pose_display",
                default=_t("Not set"),
            ),
            SettingField(
                "safe_travel_set_current",
                _t("Calibration to Paint"),
                "paint_action_button",
                default=_t("Set Current Calibration-to-Paint Pose"),
            ),
            _toggle("dropoff_safe_travel_enabled", "Use Waypoint Between Paint and Dropoff"),
            SettingField(
                "dropoff_safe_travel_position",
                _t("Paint to Dropoff Pose"),
                "paint_pose_display",
                default=_t("Not set"),
            ),
            SettingField(
                "dropoff_safe_travel_set_current",
                _t("Paint to Dropoff"),
                "paint_action_button",
                default=_t("Set Current Paint-to-Dropoff Pose"),
            ),
        ]),
    ]


def build_motion_speed_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Pickup"), [
            _percent_field("pickup_approach_vel_percent", "Approach Velocity"),
            _percent_field("pickup_approach_acc_percent", "Approach Acceleration"),
            _percent_field("pickup_descend_vel_percent", "Descend Velocity"),
            _percent_field("pickup_descend_acc_percent", "Descend Acceleration"),
            _percent_field("pickup_lift_align_vel_percent", "Lift/Align Velocity"),
            _percent_field("pickup_lift_align_acc_percent", "Lift/Align Acceleration"),
            _percent_field("pickup_change_plane_vel_percent", "Change-Plane Velocity"),
            _percent_field("pickup_change_plane_acc_percent", "Change-Plane Acceleration"),
            _percent_field("pickup_stage_transition_vel_percent", "Stage Transition Velocity"),
            _percent_field("pickup_stage_transition_acc_percent", "Stage Transition Acceleration"),
            _percent_field("pickup_first_contact_vel_percent", "First-Contact Velocity"),
            _percent_field("pickup_first_contact_acc_percent", "First-Contact Acceleration"),
        ]),
        SettingGroup(_t("Magazine Load"), [
            _percent_field("magazine_move_to_magazine_vel_percent", "Move to Magazine Velocity", 30.0),
            _percent_field("magazine_move_to_magazine_acc_percent", "Move to Magazine Acceleration", 30.0),
            _percent_field("magazine_transfer_to_calibration_vel_percent", "Magazine to Calibration Velocity", 30.0),
            _percent_field("magazine_transfer_to_calibration_acc_percent", "Magazine to Calibration Acceleration", 30.0),
        ]),
        SettingGroup(_t("Cleanup"), [
            _percent_field("cleanup_vel_percent", "Cleanup Velocity"),
            _percent_field("cleanup_acc_percent", "Cleanup Acceleration"),
        ]),
        SettingGroup(_t("Dropoff"), [
            _percent_field("dropoff_release_align_vel_percent", "Release-Align Velocity"),
            _percent_field("dropoff_release_align_acc_percent", "Release-Align Acceleration"),
        ]),
        SettingGroup(_t("Navigation"), [
            _percent_field("nav_unwind_vel_percent", "Joint 6 Unwind Velocity"),
            _percent_field("nav_unwind_acc_percent", "Joint 6 Unwind Acceleration"),
            _percent_field("nav_calibration_move_vel_percent", "Move to Calibration Velocity"),
            _percent_field("nav_calibration_move_acc_percent", "Move to Calibration Acceleration"),
        ]),
    ]


def build_distance_offset_groups() -> list[SettingGroup]:
    return [
        SettingGroup(_t("Pickup Heights"), [
            _mm_field("pickup_approach_offset_mm", "Approach Offset", min_val=0.0),
            _mm_field("pickup_contact_offset_mm", "Contact Offset", min_val=0.0),
            _mm_field("pickup_initial_lift_clearance_mm", "Initial Lift Clearance", min_val=0.0),
        ]),
        SettingGroup(_t("Cleanup Offsets"), [
            _mm_field("cleanup_z_offset_mm", "Cleanup Z Offset"),
            _mm_field("cleanup_second_pass_pivot_z_offset_mm", "Second-Pass Pivot Z Offset"),
        ]),
    ]


def build_paint_path_groups() -> list[SettingGroup]:
    return [
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
