from dataclasses import replace

from src.robot_systems.paint.processes.paint.config import (
    PaintDropoffConfig,
    PaintEdgeCleanupConfig,
    PaintNavigationReturnConfig,
    PaintProcessConfig,
    PickupMotionConfig,
)


class PaintProcessSettingsMapper:
    @staticmethod
    def _pose_to_text(position: object) -> str:
        if not position:
            return ""
        try:
            values = [float(value) for value in list(position)[:6]]
        except (TypeError, ValueError):
            return ""
        if len(values) < 6:
            return ""
        return ", ".join(f"{value:.3f}" for value in values)

    @staticmethod
    def _pose_from_value(value: object, fallback: list[float]) -> list[float]:
        if isinstance(value, str):
            raw_values = [part.strip() for part in value.replace("[", "").replace("]", "").split(",")]
        else:
            try:
                raw_values = list(value)
            except TypeError:
                return list(fallback)
        try:
            values = [float(item) for item in raw_values[:6]]
        except (TypeError, ValueError):
            return list(fallback)
        if len(values) < 6:
            return list(fallback)
        return values

    @staticmethod
    def _waypoint_from_value(value: object, default_vel: float, default_acc: float) -> dict | None:
        if isinstance(value, dict):
            pose = PaintProcessSettingsMapper._pose_from_value(
                value.get("position", value.get("pose", [])),
                [],
            )
            if not pose:
                return None
            try:
                vel = float(value.get("vel_percent", default_vel))
                acc = float(value.get("acc_percent", default_acc))
                blend_r = float(value.get("blendR", value.get("blend_r", 0.0)))
            except (TypeError, ValueError):
                vel = float(default_vel)
                acc = float(default_acc)
                blend_r = 0.0
            return {
                "position": pose,
                "vel_percent": vel,
                "acc_percent": acc,
                "motion_type": PaintProcessSettingsMapper._motion_type_from_value(
                    value.get("motion_type", value.get("type", "ptp"))
                ),
                "blendR": max(0.0, blend_r),
            }

        pose = PaintProcessSettingsMapper._pose_from_value(value, [])
        if not pose:
            return None
        vel = float(default_vel)
        acc = float(default_acc)
        motion_type = "ptp"
        blend_r = 0.0
        try:
            raw = list(value)
            if len(raw) >= 8:
                vel = float(raw[6])
                acc = float(raw[7])
            if len(raw) >= 9:
                motion_type = PaintProcessSettingsMapper._motion_type_from_value(raw[8])
            if len(raw) >= 10:
                blend_r = float(raw[9])
        except (TypeError, ValueError):
            pass
        return {
            "position": pose,
            "vel_percent": vel,
            "acc_percent": acc,
            "motion_type": motion_type,
            "blendR": max(0.0, blend_r),
        }

    @staticmethod
    def _motion_type_from_value(value: object) -> str:
        motion_type = str(value or "ptp").strip().lower()
        return motion_type if motion_type in {"ptp", "linear", "fast_lin"} else "ptp"

    @staticmethod
    def _profile_from_config(config: object, key: str, label: str, vel_attr: str, acc_attr: str) -> dict:
        return {
            "key": key,
            "label": label,
            "vel_percent": float(getattr(config, vel_attr)),
            "acc_percent": float(getattr(config, acc_attr)),
            "motion_type": PaintProcessSettingsMapper._motion_type_from_value(
                getattr(config, f"{key}_motion_type", getattr(config, "motion_type", "ptp"))
            ),
            "blendR": max(0.0, float(getattr(config, f"{key}_blendR", getattr(config, "blendR", 0.0)))),
        }

    @staticmethod
    def _profiles_by_key(value: object) -> dict[str, dict]:
        try:
            items = list(value or [])
        except TypeError:
            return {}
        profiles: dict[str, dict] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", "")).strip()
            if not key:
                continue
            try:
                vel = float(item.get("vel_percent", 0.0))
                acc = float(item.get("acc_percent", 0.0))
                blend_r = float(item.get("blendR", item.get("blend_r", 0.0)))
            except (TypeError, ValueError):
                continue
            profiles[key] = {
                "vel_percent": vel,
                "acc_percent": acc,
                "motion_type": PaintProcessSettingsMapper._motion_type_from_value(
                    item.get("motion_type", item.get("type", "ptp"))
                ),
                "blendR": max(0.0, blend_r),
            }
        return profiles

    @staticmethod
    def _profile_value(
        profiles: dict[str, dict],
        key: str,
        attr: str,
        flat: dict,
        legacy_key: str,
        fallback: object,
    ) -> object:
        if key in profiles and attr in profiles[key]:
            return profiles[key][attr]
        return flat.get(legacy_key, fallback)

    @staticmethod
    def _waypoint_list_from_value(value: object, fallback: list[dict], default_vel: float, default_acc: float) -> list[dict]:
        if not value:
            return [dict(item) for item in fallback]
        if isinstance(value, str):
            waypoint = PaintProcessSettingsMapper._waypoint_from_value(value, default_vel, default_acc)
            return [waypoint] if waypoint is not None else [dict(item) for item in fallback]
        waypoints: list[dict] = []
        try:
            items = list(value)
        except TypeError:
            return [dict(item) for item in fallback]
        for item in items:
            waypoint = PaintProcessSettingsMapper._waypoint_from_value(item, default_vel, default_acc)
            if waypoint is not None:
                waypoints.append(waypoint)
        return waypoints

    @staticmethod
    def _configured_waypoints(positions: object, position: object, default_vel: float, default_acc: float) -> list[dict]:
        result = PaintProcessSettingsMapper._waypoint_list_from_value(positions, [], default_vel, default_acc)
        if result:
            return result
        single = PaintProcessSettingsMapper._waypoint_from_value(position, default_vel, default_acc)
        return [single] if single is not None else []

    @staticmethod
    def to_flat_dict(settings: PaintProcessConfig) -> dict:
        pickup = settings.pickup_motion
        staging = settings.contact_staging
        cleanup = settings.edge_cleanup
        dropoff = settings.dropoff
        magazine = settings.magazine_load
        safe_travel = settings.safe_travel
        dropoff_safe_travel = settings.dropoff_safe_travel
        nav = settings.navigation_return
        interpolation = settings.interpolation
        return {
            "enable_vacuum_pump": settings.enable_vacuum_pump,
            "apply_camera_to_tcp_for_pickup": settings.apply_camera_to_tcp_for_pickup,
            "enable_z_shift_pixel_compensation": settings.enable_z_shift_pixel_compensation,
            "contour_pixel_to_mm_mode": settings.contour_pixel_to_mm_mode,
            "pivot_motion_plane": settings.pivot_motion_plane,
            "primary_group_id": settings.primary_group_id,
            "secondary_group_id": settings.secondary_group_id,
            "cleanup_group_id": settings.cleanup_group_id,
            "pivot_axis": settings.pivot_axis,
            "pivot_direction": settings.pivot_direction,
            "pivot_contact_side": settings.pivot_contact_side,
            "mirror_xz_ry_execution_rotation_value": settings.mirror_xz_ry_execution_rotation_value,
            "pickup_axis_alignment_sign_value": settings.pickup_axis_alignment_sign_value,
            "run_while_workpiece_found": settings.run_while_workpiece_found,
            "enable_workpiece_matching": settings.enable_workpiece_matching,
            "default_paint_velocity_percent": settings.default_paint_velocity_percent,
            "default_paint_acceleration_percent": settings.default_paint_acceleration_percent,
            "default_paint_offset_mm": settings.default_paint_offset_mm,
            "closed_contour_overlap_mm": settings.closed_contour_overlap_mm,
            "enable_execution_state_timing": settings.enable_execution_state_timing,
            "pause_dashboard_live_view_after_capture": settings.pause_dashboard_live_view_after_capture,
            "combine_change_plane_with_first_contact": pickup.combine_change_plane_with_first_contact,
            "pickup_approach_offset_mm": pickup.approach_offset_mm,
            "pickup_contact_offset_mm": pickup.contact_offset_mm,
            "pickup_initial_lift_clearance_mm": pickup.initial_lift_clearance_mm,
            "staging_attach_z_offset_mm": staging.attach_z_offset_mm,
            "staging_attach_vel_percent": staging.attach_vel_percent,
            "staging_attach_acc_percent": staging.attach_acc_percent,
            "staging_attach_paint_axis_offset_mm": staging.attach_paint_axis_offset_mm,
            "staging_attach_perpendicular_axis_offset_mm": staging.attach_perpendicular_axis_offset_mm,
            "staging_detach_z_offset_mm": staging.detach_z_offset_mm,
            "staging_detach_paint_axis_offset_mm": staging.detach_paint_axis_offset_mm,
            "staging_detach_perpendicular_axis_offset_mm": staging.detach_perpendicular_axis_offset_mm,
            "pickup_contact_mode": pickup.pickup_contact_mode,
            "pickup_servo_contact_linear_mm_s": pickup.servo_contact_linear_mm_s,
            "pickup_servo_contact_min_z_mm": pickup.servo_contact_min_z_mm,
            "pickup_servo_contact_retract_linear_mm_s": pickup.servo_contact_retract_linear_mm_s,
            "pickup_servo_contact_retract_final_linear_mm_s": pickup.servo_contact_retract_final_linear_mm_s,
            "pickup_servo_contact_retract_slowdown_clearance_mm": pickup.servo_contact_retract_slowdown_clearance_mm,
            "pickup_servo_contact_retract_safety_margin_mm": pickup.servo_contact_retract_safety_margin_mm,
            "pickup_servo_contact_timeout_s": pickup.servo_contact_timeout_s,
            "pickup_servo_contact_poll_interval_s": pickup.servo_contact_poll_interval_s,
            "pickup_servo_contact_preflight_read_attempts": pickup.servo_contact_preflight_read_attempts,
            "pickup_servo_contact_read_failure_limit": pickup.servo_contact_read_failure_limit,
            "pickup_servo_contact_fallback_to_planned_descend": pickup.servo_contact_fallback_to_planned_descend,
            "pickup_servo_contact_dummy_sensor_enabled": pickup.servo_contact_dummy_sensor_enabled,
            "pickup_servo_contact_dummy_detect_after_s": pickup.servo_contact_dummy_detect_after_s,
            "pickup_approach_vel_percent": pickup.approach_vel_percent,
            "pickup_approach_acc_percent": pickup.approach_acc_percent,
            "pickup_descend_vel_percent": pickup.descend_vel_percent,
            "pickup_descend_acc_percent": pickup.descend_acc_percent,
            "pickup_lift_align_vel_percent": pickup.lift_align_vel_percent,
            "pickup_lift_align_acc_percent": pickup.lift_align_acc_percent,
            "pickup_change_plane_vel_percent": pickup.change_plane_vel_percent,
            "pickup_change_plane_acc_percent": pickup.change_plane_acc_percent,
            "pickup_stage_transition_vel_percent": pickup.stage_transition_vel_percent,
            "pickup_stage_transition_acc_percent": pickup.stage_transition_acc_percent,
            "pickup_first_contact_vel_percent": pickup.first_contact_vel_percent,
            "pickup_first_contact_acc_percent": pickup.first_contact_acc_percent,
            "pickup_motion_profiles": [
                PaintProcessSettingsMapper._profile_from_config(pickup, "approach", "Approach", "approach_vel_percent", "approach_acc_percent"),
                PaintProcessSettingsMapper._profile_from_config(pickup, "descend", "Descend", "descend_vel_percent", "descend_acc_percent"),
                PaintProcessSettingsMapper._profile_from_config(pickup, "lift_align", "Lift/Align", "lift_align_vel_percent", "lift_align_acc_percent"),
                PaintProcessSettingsMapper._profile_from_config(pickup, "change_plane", "Change Plane", "change_plane_vel_percent", "change_plane_acc_percent"),
                PaintProcessSettingsMapper._profile_from_config(pickup, "stage_transition", "Stage Transition", "stage_transition_vel_percent", "stage_transition_acc_percent"),
                PaintProcessSettingsMapper._profile_from_config(pickup, "first_contact", "First Contact", "first_contact_vel_percent", "first_contact_acc_percent"),
            ],
            "cleanup_enabled_after_xz_ry": cleanup.enabled_after_xz_ry,
            "cleanup_enabled_after_xy_rz": cleanup.enabled_after_xy_rz,
            "cleanup_enable_second_pass": cleanup.enable_second_pass,
            "cleanup_vel_percent": cleanup.vel_percent,
            "cleanup_acc_percent": cleanup.acc_percent,
            "cleanup_motion_profiles": [
                PaintProcessSettingsMapper._profile_from_config(cleanup, "cleanup", "Cleanup", "vel_percent", "acc_percent"),
            ],
            "cleanup_spacing_mm": cleanup.spacing_mm,
            "cleanup_z_offset_mm": cleanup.z_offset_mm,
            "cleanup_perpendicular_retreat_offset_mm": cleanup.perpendicular_retreat_offset_mm,
            "cleanup_second_pass_pivot_z_offset_mm": cleanup.second_pass_pivot_z_offset_mm,
            "dropoff_strategy": dropoff.strategy,
            "dropoff_allow_sub_zero": dropoff.allow_sub_zero_dropoff,
            "dropoff_corridor_x_margin_mm": dropoff.corridor_x_margin_mm,
            "dropoff_corridor_y_margin_mm": dropoff.corridor_y_margin_mm,
            "dropoff_corridor_z_tolerance_mm": dropoff.corridor_z_tolerance_mm,
            "dropoff_corridor_entry_z_max_mm": dropoff.corridor_entry_z_max_mm,
            "dropoff_corridor_maximum_velocity_percent": dropoff.corridor_maximum_velocity_percent,
            "dropoff_corridor_maximum_acceleration_percent": dropoff.corridor_maximum_acceleration_percent,
            "dropoff_sub_zero_approach_z_mm": dropoff.sub_zero_approach_z_mm,
            "dropoff_release_align_vel_percent": dropoff.release_align_vel_percent,
            "dropoff_release_align_acc_percent": dropoff.release_align_acc_percent,
            "dropoff_motion_profiles": [
                PaintProcessSettingsMapper._profile_from_config(
                    dropoff,
                    "release_align",
                    "Release Align",
                    "release_align_vel_percent",
                    "release_align_acc_percent",
                ),
            ],
            "magazine_load_enabled": magazine.enabled,
            "magazine_pickup_mode": magazine.pickup_mode,
            "magazine_fixed_pickup_group_id": magazine.fixed_pickup_group_id,
            "magazine_fixed_pickup_position_tolerance_mm": magazine.fixed_pickup_position_tolerance_mm,
            "magazine_fixed_pickup_orientation_tolerance_deg": magazine.fixed_pickup_orientation_tolerance_deg,
            "magazine_release_z_mm": magazine.release_z_mm,
            "magazine_camera_settle_s": magazine.camera_settle_s,
            "magazine_release_settle_s": magazine.release_settle_s,
            "magazine_move_to_magazine_vel_percent": magazine.move_to_magazine_vel_percent,
            "magazine_move_to_magazine_acc_percent": magazine.move_to_magazine_acc_percent,
            "magazine_transfer_to_calibration_vel_percent": magazine.transfer_to_calibration_vel_percent,
            "magazine_transfer_to_calibration_acc_percent": magazine.transfer_to_calibration_acc_percent,
            "magazine_motion_profiles": [
                PaintProcessSettingsMapper._profile_from_config(
                    magazine,
                    "move_to_magazine",
                    "Move to Magazine",
                    "move_to_magazine_vel_percent",
                    "move_to_magazine_acc_percent",
                ),
                PaintProcessSettingsMapper._profile_from_config(
                    magazine,
                    "transfer_to_calibration",
                    "Magazine to Calibration",
                    "transfer_to_calibration_vel_percent",
                    "transfer_to_calibration_acc_percent",
                ),
            ],
            "safe_travel_enabled": safe_travel.enabled,
            "safe_travel_position": PaintProcessSettingsMapper._pose_to_text(safe_travel.position),
            "safe_travel_positions": PaintProcessSettingsMapper._configured_waypoints(
                safe_travel.positions,
                safe_travel.position,
                pickup.stage_transition_vel_percent,
                pickup.stage_transition_acc_percent,
            ),
            "dropoff_safe_travel_enabled": dropoff_safe_travel.enabled,
            "dropoff_safe_travel_position": PaintProcessSettingsMapper._pose_to_text(dropoff_safe_travel.position),
            "dropoff_safe_travel_positions": PaintProcessSettingsMapper._configured_waypoints(
                dropoff_safe_travel.positions,
                dropoff_safe_travel.position,
                dropoff.release_align_vel_percent,
                dropoff.release_align_acc_percent,
            ),
            "nav_unwind_vel_percent": nav.unwind_vel_percent,
            "nav_unwind_acc_percent": nav.unwind_acc_percent,
            "nav_unwind_queue_if_busy": nav.unwind_queue_if_busy,
            "nav_calibration_move_vel_percent": nav.calibration_move_vel_percent,
            "nav_calibration_move_acc_percent": nav.calibration_move_acc_percent,
            "navigation_motion_profiles": [
                PaintProcessSettingsMapper._profile_from_config(
                    nav,
                    "calibration_move",
                    "Move to Calibration",
                    "calibration_move_vel_percent",
                    "calibration_move_acc_percent",
                ),
            ],
            "path_tangent_lookahead_mm": interpolation.path_tangent_lookahead_mm,
            "path_tangent_deadband_deg": interpolation.path_tangent_deadband_deg,
            "enable_pivot_debug_plot": settings.enable_pivot_debug_plot,
            "enable_path_debug_plots": settings.enable_path_debug_plots,
            "enable_execution_motion_trace": settings.enable_execution_motion_trace,
            "execution_motion_trace_sample_period_s": settings.execution_motion_trace_sample_period_s,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: PaintProcessConfig) -> PaintProcessConfig:
        pickup_profiles = PaintProcessSettingsMapper._profiles_by_key(flat.get("pickup_motion_profiles"))
        cleanup_profiles = PaintProcessSettingsMapper._profiles_by_key(flat.get("cleanup_motion_profiles"))
        dropoff_profiles = PaintProcessSettingsMapper._profiles_by_key(flat.get("dropoff_motion_profiles"))
        magazine_profiles = PaintProcessSettingsMapper._profiles_by_key(flat.get("magazine_motion_profiles"))
        navigation_profiles = PaintProcessSettingsMapper._profiles_by_key(flat.get("navigation_motion_profiles"))
        pickup = replace(
            base.pickup_motion,
            approach_offset_mm=float(flat.get("pickup_approach_offset_mm", base.pickup_motion.approach_offset_mm)),
            contact_offset_mm=float(flat.get("pickup_contact_offset_mm", base.pickup_motion.contact_offset_mm)),
            initial_lift_clearance_mm=float(
                flat.get("pickup_initial_lift_clearance_mm", base.pickup_motion.initial_lift_clearance_mm)
            ),
            pickup_contact_mode=str(
                flat.get("pickup_contact_mode", base.pickup_motion.pickup_contact_mode)
            ),
            servo_contact_linear_mm_s=float(
                flat.get("pickup_servo_contact_linear_mm_s", base.pickup_motion.servo_contact_linear_mm_s)
            ),
            servo_contact_min_z_mm=float(
                flat.get("pickup_servo_contact_min_z_mm", base.pickup_motion.servo_contact_min_z_mm)
            ),
            servo_contact_retract_linear_mm_s=float(
                flat.get("pickup_servo_contact_retract_linear_mm_s", base.pickup_motion.servo_contact_retract_linear_mm_s)
            ),
            servo_contact_retract_final_linear_mm_s=float(
                flat.get(
                    "pickup_servo_contact_retract_final_linear_mm_s",
                    base.pickup_motion.servo_contact_retract_final_linear_mm_s,
                )
            ),
            servo_contact_retract_slowdown_clearance_mm=float(
                flat.get(
                    "pickup_servo_contact_retract_slowdown_clearance_mm",
                    base.pickup_motion.servo_contact_retract_slowdown_clearance_mm,
                )
            ),
            servo_contact_retract_safety_margin_mm=float(
                flat.get(
                    "pickup_servo_contact_retract_safety_margin_mm",
                    base.pickup_motion.servo_contact_retract_safety_margin_mm,
                )
            ),
            servo_contact_timeout_s=float(
                flat.get("pickup_servo_contact_timeout_s", base.pickup_motion.servo_contact_timeout_s)
            ),
            servo_contact_poll_interval_s=float(
                flat.get("pickup_servo_contact_poll_interval_s", base.pickup_motion.servo_contact_poll_interval_s)
            ),
            servo_contact_preflight_read_attempts=int(
                flat.get(
                    "pickup_servo_contact_preflight_read_attempts",
                    base.pickup_motion.servo_contact_preflight_read_attempts,
                )
            ),
            servo_contact_read_failure_limit=int(
                flat.get(
                    "pickup_servo_contact_read_failure_limit",
                    base.pickup_motion.servo_contact_read_failure_limit,
                )
            ),
            servo_contact_fallback_to_planned_descend=bool(
                flat.get(
                    "pickup_servo_contact_fallback_to_planned_descend",
                    base.pickup_motion.servo_contact_fallback_to_planned_descend,
                )
            ),
            servo_contact_dummy_sensor_enabled=bool(
                flat.get(
                    "pickup_servo_contact_dummy_sensor_enabled",
                    base.pickup_motion.servo_contact_dummy_sensor_enabled,
                )
            ),
            servo_contact_dummy_detect_after_s=float(
                flat.get(
                    "pickup_servo_contact_dummy_detect_after_s",
                    base.pickup_motion.servo_contact_dummy_detect_after_s,
                )
            ),
            approach_vel_percent=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "approach", "vel_percent", flat, "pickup_approach_vel_percent", base.pickup_motion.approach_vel_percent)),
            approach_acc_percent=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "approach", "acc_percent", flat, "pickup_approach_acc_percent", base.pickup_motion.approach_acc_percent)),
            approach_motion_type=str(PaintProcessSettingsMapper._profile_value(pickup_profiles, "approach", "motion_type", flat, "pickup_approach_motion_type", base.pickup_motion.approach_motion_type)),
            approach_blendR=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "approach", "blendR", flat, "pickup_approach_blendR", base.pickup_motion.approach_blendR)),
            descend_vel_percent=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "descend", "vel_percent", flat, "pickup_descend_vel_percent", base.pickup_motion.descend_vel_percent)),
            descend_acc_percent=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "descend", "acc_percent", flat, "pickup_descend_acc_percent", base.pickup_motion.descend_acc_percent)),
            descend_motion_type=str(PaintProcessSettingsMapper._profile_value(pickup_profiles, "descend", "motion_type", flat, "pickup_descend_motion_type", base.pickup_motion.descend_motion_type)),
            descend_blendR=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "descend", "blendR", flat, "pickup_descend_blendR", base.pickup_motion.descend_blendR)),
            lift_align_vel_percent=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "lift_align", "vel_percent", flat, "pickup_lift_align_vel_percent", base.pickup_motion.lift_align_vel_percent)),
            lift_align_acc_percent=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "lift_align", "acc_percent", flat, "pickup_lift_align_acc_percent", base.pickup_motion.lift_align_acc_percent)),
            lift_align_motion_type=str(PaintProcessSettingsMapper._profile_value(pickup_profiles, "lift_align", "motion_type", flat, "pickup_lift_align_motion_type", base.pickup_motion.lift_align_motion_type)),
            lift_align_blendR=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "lift_align", "blendR", flat, "pickup_lift_align_blendR", base.pickup_motion.lift_align_blendR)),
            change_plane_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(pickup_profiles, "change_plane", "vel_percent", flat, "pickup_change_plane_vel_percent", base.pickup_motion.change_plane_vel_percent)
            ),
            change_plane_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(pickup_profiles, "change_plane", "acc_percent", flat, "pickup_change_plane_acc_percent", base.pickup_motion.change_plane_acc_percent)
            ),
            change_plane_motion_type=str(PaintProcessSettingsMapper._profile_value(pickup_profiles, "change_plane", "motion_type", flat, "pickup_change_plane_motion_type", base.pickup_motion.change_plane_motion_type)),
            change_plane_blendR=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "change_plane", "blendR", flat, "pickup_change_plane_blendR", base.pickup_motion.change_plane_blendR)),
            combine_change_plane_with_first_contact=bool(
                flat.get(
                    "combine_change_plane_with_first_contact",
                    base.pickup_motion.combine_change_plane_with_first_contact,
                )
            ),
            stage_transition_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(pickup_profiles, "stage_transition", "vel_percent", flat, "pickup_stage_transition_vel_percent", base.pickup_motion.stage_transition_vel_percent)
            ),
            stage_transition_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(pickup_profiles, "stage_transition", "acc_percent", flat, "pickup_stage_transition_acc_percent", base.pickup_motion.stage_transition_acc_percent)
            ),
            stage_transition_motion_type=str(PaintProcessSettingsMapper._profile_value(pickup_profiles, "stage_transition", "motion_type", flat, "pickup_stage_transition_motion_type", base.pickup_motion.stage_transition_motion_type)),
            stage_transition_blendR=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "stage_transition", "blendR", flat, "pickup_stage_transition_blendR", base.pickup_motion.stage_transition_blendR)),
            first_contact_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(pickup_profiles, "first_contact", "vel_percent", flat, "pickup_first_contact_vel_percent", base.pickup_motion.first_contact_vel_percent)
            ),
            first_contact_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(pickup_profiles, "first_contact", "acc_percent", flat, "pickup_first_contact_acc_percent", base.pickup_motion.first_contact_acc_percent)
            ),
            first_contact_motion_type=str(PaintProcessSettingsMapper._profile_value(pickup_profiles, "first_contact", "motion_type", flat, "pickup_first_contact_motion_type", base.pickup_motion.first_contact_motion_type)),
            first_contact_blendR=float(PaintProcessSettingsMapper._profile_value(pickup_profiles, "first_contact", "blendR", flat, "pickup_first_contact_blendR", base.pickup_motion.first_contact_blendR)),
        )
        staging = replace(
            base.contact_staging,
            attach_vel_percent=float(
                flat.get("staging_attach_vel_percent", base.contact_staging.attach_vel_percent)
            ),
            attach_acc_percent=float(
                flat.get("staging_attach_acc_percent", base.contact_staging.attach_acc_percent)
            ),
            attach_z_offset_mm=float(
                flat.get("staging_attach_z_offset_mm", base.contact_staging.attach_z_offset_mm)
            ),
            attach_paint_axis_offset_mm=float(
                flat.get(
                    "staging_attach_paint_axis_offset_mm",
                    base.contact_staging.attach_paint_axis_offset_mm,
                )
            ),
            attach_perpendicular_axis_offset_mm=float(
                flat.get(
                    "staging_attach_perpendicular_axis_offset_mm",
                    base.contact_staging.attach_perpendicular_axis_offset_mm,
                )
            ),
            detach_z_offset_mm=float(
                flat.get("staging_detach_z_offset_mm", base.contact_staging.detach_z_offset_mm)
            ),
            detach_paint_axis_offset_mm=float(
                flat.get(
                    "staging_detach_paint_axis_offset_mm",
                    base.contact_staging.detach_paint_axis_offset_mm,
                )
            ),
            detach_perpendicular_axis_offset_mm=float(
                flat.get(
                    "staging_detach_perpendicular_axis_offset_mm",
                    base.contact_staging.detach_perpendicular_axis_offset_mm,
                )
            ),
        )
        cleanup = replace(
            base.edge_cleanup,
            enabled_after_xz_ry=bool(flat.get("cleanup_enabled_after_xz_ry", base.edge_cleanup.enabled_after_xz_ry)),
            enabled_after_xy_rz=bool(flat.get("cleanup_enabled_after_xy_rz", base.edge_cleanup.enabled_after_xy_rz)),
            enable_second_pass=bool(flat.get("cleanup_enable_second_pass", base.edge_cleanup.enable_second_pass)),
            vel_percent=float(PaintProcessSettingsMapper._profile_value(cleanup_profiles, "cleanup", "vel_percent", flat, "cleanup_vel_percent", base.edge_cleanup.vel_percent)),
            acc_percent=float(PaintProcessSettingsMapper._profile_value(cleanup_profiles, "cleanup", "acc_percent", flat, "cleanup_acc_percent", base.edge_cleanup.acc_percent)),
            motion_type=str(PaintProcessSettingsMapper._profile_value(cleanup_profiles, "cleanup", "motion_type", flat, "cleanup_motion_type", base.edge_cleanup.motion_type)),
            blendR=float(PaintProcessSettingsMapper._profile_value(cleanup_profiles, "cleanup", "blendR", flat, "cleanup_blendR", base.edge_cleanup.blendR)),
            spacing_mm=float(flat.get("cleanup_spacing_mm", base.edge_cleanup.spacing_mm)),
            z_offset_mm=float(flat.get("cleanup_z_offset_mm", base.edge_cleanup.z_offset_mm)),
            perpendicular_retreat_offset_mm=float(
                flat.get(
                    "cleanup_perpendicular_retreat_offset_mm",
                    base.edge_cleanup.perpendicular_retreat_offset_mm,
                )
            ),
            second_pass_pivot_z_offset_mm=float(
                flat.get("cleanup_second_pass_pivot_z_offset_mm", base.edge_cleanup.second_pass_pivot_z_offset_mm)
            ),
        )
        dropoff = replace(
            base.dropoff,
            strategy=str(flat.get("dropoff_strategy", base.dropoff.strategy)),
            allow_sub_zero_dropoff=bool(
                flat.get("dropoff_allow_sub_zero", base.dropoff.allow_sub_zero_dropoff)
            ),
            corridor_x_margin_mm=float(
                flat.get("dropoff_corridor_x_margin_mm", base.dropoff.corridor_x_margin_mm)
            ),
            corridor_y_margin_mm=float(
                flat.get("dropoff_corridor_y_margin_mm", base.dropoff.corridor_y_margin_mm)
            ),
            corridor_z_tolerance_mm=float(
                flat.get("dropoff_corridor_z_tolerance_mm", base.dropoff.corridor_z_tolerance_mm)
            ),
            corridor_entry_z_max_mm=float(
                flat.get("dropoff_corridor_entry_z_max_mm", base.dropoff.corridor_entry_z_max_mm)
            ),
            corridor_maximum_velocity_percent=float(
                flat.get(
                    "dropoff_corridor_maximum_velocity_percent",
                    base.dropoff.corridor_maximum_velocity_percent,
                )
            ),
            corridor_maximum_acceleration_percent=float(
                flat.get(
                    "dropoff_corridor_maximum_acceleration_percent",
                    base.dropoff.corridor_maximum_acceleration_percent,
                )
            ),
            sub_zero_approach_z_mm=float(
                flat.get(
                    "dropoff_sub_zero_approach_z_mm",
                    base.dropoff.sub_zero_approach_z_mm,
                )
            ),
            release_align_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(dropoff_profiles, "release_align", "vel_percent", flat, "dropoff_release_align_vel_percent", base.dropoff.release_align_vel_percent)
            ),
            release_align_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(dropoff_profiles, "release_align", "acc_percent", flat, "dropoff_release_align_acc_percent", base.dropoff.release_align_acc_percent)
            ),
            release_align_motion_type=str(PaintProcessSettingsMapper._profile_value(dropoff_profiles, "release_align", "motion_type", flat, "dropoff_release_align_motion_type", base.dropoff.release_align_motion_type)),
            release_align_blendR=float(PaintProcessSettingsMapper._profile_value(dropoff_profiles, "release_align", "blendR", flat, "dropoff_release_align_blendR", base.dropoff.release_align_blendR)),
        )
        magazine = replace(
            base.magazine_load,
            enabled=bool(flat.get("magazine_load_enabled", base.magazine_load.enabled)),
            pickup_mode=str(
                flat.get("magazine_pickup_mode", base.magazine_load.pickup_mode)
            ),
            fixed_pickup_group_id=str(
                flat.get("magazine_fixed_pickup_group_id", base.magazine_load.fixed_pickup_group_id)
            ).strip(),
            fixed_pickup_position_tolerance_mm=float(
                flat.get(
                    "magazine_fixed_pickup_position_tolerance_mm",
                    base.magazine_load.fixed_pickup_position_tolerance_mm,
                )
            ),
            fixed_pickup_orientation_tolerance_deg=float(
                flat.get(
                    "magazine_fixed_pickup_orientation_tolerance_deg",
                    base.magazine_load.fixed_pickup_orientation_tolerance_deg,
                )
            ),
            release_z_mm=float(flat.get("magazine_release_z_mm", base.magazine_load.release_z_mm)),
            camera_settle_s=float(flat.get("magazine_camera_settle_s", base.magazine_load.camera_settle_s)),
            release_settle_s=float(flat.get("magazine_release_settle_s", base.magazine_load.release_settle_s)),
            move_to_magazine_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(magazine_profiles, "move_to_magazine", "vel_percent", flat, "magazine_move_to_magazine_vel_percent", base.magazine_load.move_to_magazine_vel_percent)
            ),
            move_to_magazine_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(magazine_profiles, "move_to_magazine", "acc_percent", flat, "magazine_move_to_magazine_acc_percent", base.magazine_load.move_to_magazine_acc_percent)
            ),
            move_to_magazine_motion_type=str(PaintProcessSettingsMapper._profile_value(magazine_profiles, "move_to_magazine", "motion_type", flat, "magazine_move_to_magazine_motion_type", base.magazine_load.move_to_magazine_motion_type)),
            move_to_magazine_blendR=float(PaintProcessSettingsMapper._profile_value(magazine_profiles, "move_to_magazine", "blendR", flat, "magazine_move_to_magazine_blendR", base.magazine_load.move_to_magazine_blendR)),
            transfer_to_calibration_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(magazine_profiles, "transfer_to_calibration", "vel_percent", flat, "magazine_transfer_to_calibration_vel_percent", base.magazine_load.transfer_to_calibration_vel_percent)
            ),
            transfer_to_calibration_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(magazine_profiles, "transfer_to_calibration", "acc_percent", flat, "magazine_transfer_to_calibration_acc_percent", base.magazine_load.transfer_to_calibration_acc_percent)
            ),
            transfer_to_calibration_motion_type=str(PaintProcessSettingsMapper._profile_value(magazine_profiles, "transfer_to_calibration", "motion_type", flat, "magazine_transfer_to_calibration_motion_type", base.magazine_load.transfer_to_calibration_motion_type)),
            transfer_to_calibration_blendR=float(PaintProcessSettingsMapper._profile_value(magazine_profiles, "transfer_to_calibration", "blendR", flat, "magazine_transfer_to_calibration_blendR", base.magazine_load.transfer_to_calibration_blendR)),
        )
        safe_travel = replace(
            base.safe_travel,
            enabled=bool(flat.get("safe_travel_enabled", base.safe_travel.enabled)),
            positions=PaintProcessSettingsMapper._waypoint_list_from_value(
                flat.get("safe_travel_positions") or flat.get("safe_travel_position", base.safe_travel.positions),
                PaintProcessSettingsMapper._configured_waypoints(
                    base.safe_travel.positions,
                    base.safe_travel.position,
                    base.pickup_motion.stage_transition_vel_percent,
                    base.pickup_motion.stage_transition_acc_percent,
                ),
                pickup.stage_transition_vel_percent,
                pickup.stage_transition_acc_percent,
            ),
        )
        safe_travel = replace(
            safe_travel,
            position=list(safe_travel.positions[0]["position"]) if safe_travel.positions else [],
        )
        dropoff_safe_travel = replace(
            base.dropoff_safe_travel,
            enabled=bool(flat.get("dropoff_safe_travel_enabled", base.dropoff_safe_travel.enabled)),
            positions=PaintProcessSettingsMapper._waypoint_list_from_value(
                flat.get("dropoff_safe_travel_positions")
                or flat.get("dropoff_safe_travel_position", base.dropoff_safe_travel.positions),
                PaintProcessSettingsMapper._configured_waypoints(
                    base.dropoff_safe_travel.positions,
                    base.dropoff_safe_travel.position,
                    base.dropoff.release_align_vel_percent,
                    base.dropoff.release_align_acc_percent,
                ),
                dropoff.release_align_vel_percent,
                dropoff.release_align_acc_percent,
            ),
        )
        dropoff_safe_travel = replace(
            dropoff_safe_travel,
            position=list(dropoff_safe_travel.positions[0]["position"]) if dropoff_safe_travel.positions else [],
        )
        nav = replace(
            base.navigation_return,
            unwind_vel_percent=float(flat.get("nav_unwind_vel_percent", base.navigation_return.unwind_vel_percent)),
            unwind_acc_percent=float(flat.get("nav_unwind_acc_percent", base.navigation_return.unwind_acc_percent)),
            unwind_queue_if_busy=bool(flat.get("nav_unwind_queue_if_busy", base.navigation_return.unwind_queue_if_busy)),
            calibration_move_vel_percent=float(
                PaintProcessSettingsMapper._profile_value(navigation_profiles, "calibration_move", "vel_percent", flat, "nav_calibration_move_vel_percent", base.navigation_return.calibration_move_vel_percent)
            ),
            calibration_move_acc_percent=float(
                PaintProcessSettingsMapper._profile_value(navigation_profiles, "calibration_move", "acc_percent", flat, "nav_calibration_move_acc_percent", base.navigation_return.calibration_move_acc_percent)
            ),
            calibration_move_motion_type=str(PaintProcessSettingsMapper._profile_value(navigation_profiles, "calibration_move", "motion_type", flat, "nav_calibration_move_motion_type", base.navigation_return.calibration_move_motion_type)),
            calibration_move_blendR=float(PaintProcessSettingsMapper._profile_value(navigation_profiles, "calibration_move", "blendR", flat, "nav_calibration_move_blendR", base.navigation_return.calibration_move_blendR)),
        )
        interpolation = replace(
            base.interpolation,
            path_tangent_lookahead_mm=float(
                flat.get("path_tangent_lookahead_mm", base.interpolation.path_tangent_lookahead_mm)
            ),
            path_tangent_deadband_deg=float(
                flat.get("path_tangent_deadband_deg", base.interpolation.path_tangent_deadband_deg)
            ),
        )
        return replace(
            base,
            enable_z_shift_pixel_compensation=bool(
                flat.get("enable_z_shift_pixel_compensation", base.enable_z_shift_pixel_compensation)
            ),
            contour_pixel_to_mm_mode=str(flat.get("contour_pixel_to_mm_mode", base.contour_pixel_to_mm_mode)),
            enable_execution_motion_trace=bool(
                flat.get("enable_execution_motion_trace", base.enable_execution_motion_trace)
            ),
            execution_motion_trace_sample_period_s=float(
                flat.get(
                    "execution_motion_trace_sample_period_s",
                    base.execution_motion_trace_sample_period_s,
                )
            ),
            pivot_motion_plane=str(flat.get("pivot_motion_plane", base.pivot_motion_plane)),
            primary_group_id=str(flat.get("primary_group_id", base.primary_group_id)),
            secondary_group_id=str(flat.get("secondary_group_id", base.secondary_group_id)),
            cleanup_group_id=str(flat.get("cleanup_group_id", base.cleanup_group_id)),
            pivot_axis=str(flat.get("pivot_axis", base.pivot_axis)),
            pivot_direction=str(flat.get("pivot_direction", base.pivot_direction)),
            pivot_contact_side=str(flat.get("pivot_contact_side", base.pivot_contact_side)),
            mirror_xz_ry_execution_rotation_value=bool(
                flat.get("mirror_xz_ry_execution_rotation_value", base.mirror_xz_ry_execution_rotation_value)
            ),
            pickup_axis_alignment_sign_value=float(
                flat.get("pickup_axis_alignment_sign_value", base.pickup_axis_alignment_sign_value)
            ),
            enable_vacuum_pump=bool(flat.get("enable_vacuum_pump", base.enable_vacuum_pump)),
            run_while_workpiece_found=bool(
                flat.get("run_while_workpiece_found", base.run_while_workpiece_found)
            ),
            enable_workpiece_matching=bool(
                flat.get("enable_workpiece_matching", base.enable_workpiece_matching)
            ),
            default_paint_velocity_percent=float(
                flat.get(
                    "default_paint_velocity_percent",
                    base.default_paint_velocity_percent,
                )
            ),
            default_paint_acceleration_percent=float(
                flat.get(
                    "default_paint_acceleration_percent",
                    base.default_paint_acceleration_percent,
                )
            ),
            paint_process_acceleration_scale_percent=(
                base.paint_process_acceleration_scale_percent
            ),
            default_paint_offset_mm=float(
                flat.get("default_paint_offset_mm", base.default_paint_offset_mm)
            ),
            unmatched_paint_pass_count=base.unmatched_paint_pass_count,
            unmatched_second_pass=base.unmatched_second_pass,
            closed_contour_overlap_mm=max(
                0.0,
                float(flat.get("closed_contour_overlap_mm", base.closed_contour_overlap_mm)),
            ),
            enable_execution_state_timing=bool(
                flat.get("enable_execution_state_timing", base.enable_execution_state_timing)
            ),
            pause_dashboard_live_view_after_capture=bool(
                flat.get(
                    "pause_dashboard_live_view_after_capture",
                    base.pause_dashboard_live_view_after_capture,
                )
            ),
            apply_camera_to_tcp_for_pickup=bool(
                flat.get("apply_camera_to_tcp_for_pickup", base.apply_camera_to_tcp_for_pickup)
            ),
            pickup_motion=pickup,
            contact_staging=staging,
            edge_cleanup=cleanup,
            dropoff=dropoff,
            magazine_load=magazine,
            safe_travel=safe_travel,
            dropoff_safe_travel=dropoff_safe_travel,
            navigation_return=nav,
            interpolation=interpolation,
            enable_pivot_debug_plot=bool(flat.get("enable_pivot_debug_plot", base.enable_pivot_debug_plot)),
            enable_path_debug_plots=bool(flat.get("enable_path_debug_plots", base.enable_path_debug_plots)),
        )
