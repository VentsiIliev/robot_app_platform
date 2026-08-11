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
            except (TypeError, ValueError):
                vel = float(default_vel)
                acc = float(default_acc)
            return {"position": pose, "vel_percent": vel, "acc_percent": acc}

        pose = PaintProcessSettingsMapper._pose_from_value(value, [])
        if not pose:
            return None
        vel = float(default_vel)
        acc = float(default_acc)
        try:
            raw = list(value)
            if len(raw) >= 8:
                vel = float(raw[6])
                acc = float(raw[7])
        except (TypeError, ValueError):
            pass
        return {"position": pose, "vel_percent": vel, "acc_percent": acc}

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
            "pause_dashboard_live_view_after_capture": settings.pause_dashboard_live_view_after_capture,
            "combine_change_plane_with_first_contact": pickup.combine_change_plane_with_first_contact,
            "pickup_approach_offset_mm": pickup.approach_offset_mm,
            "pickup_contact_offset_mm": pickup.contact_offset_mm,
            "pickup_initial_lift_clearance_mm": pickup.initial_lift_clearance_mm,
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
            "cleanup_enabled_after_xz_ry": cleanup.enabled_after_xz_ry,
            "cleanup_enabled_after_xy_rz": cleanup.enabled_after_xy_rz,
            "cleanup_enable_second_pass": cleanup.enable_second_pass,
            "cleanup_vel_percent": cleanup.vel_percent,
            "cleanup_acc_percent": cleanup.acc_percent,
            "cleanup_spacing_mm": cleanup.spacing_mm,
            "cleanup_z_offset_mm": cleanup.z_offset_mm,
            "cleanup_second_pass_pivot_z_offset_mm": cleanup.second_pass_pivot_z_offset_mm,
            "dropoff_strategy": dropoff.strategy,
            "dropoff_release_align_vel_percent": dropoff.release_align_vel_percent,
            "dropoff_release_align_acc_percent": dropoff.release_align_acc_percent,
            "magazine_load_enabled": magazine.enabled,
            "magazine_camera_settle_s": magazine.camera_settle_s,
            "magazine_release_settle_s": magazine.release_settle_s,
            "magazine_move_to_magazine_vel_percent": magazine.move_to_magazine_vel_percent,
            "magazine_move_to_magazine_acc_percent": magazine.move_to_magazine_acc_percent,
            "magazine_transfer_to_calibration_vel_percent": magazine.transfer_to_calibration_vel_percent,
            "magazine_transfer_to_calibration_acc_percent": magazine.transfer_to_calibration_acc_percent,
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
            "path_tangent_lookahead_mm": interpolation.path_tangent_lookahead_mm,
            "path_tangent_deadband_deg": interpolation.path_tangent_deadband_deg,
            "enable_pivot_debug_plot": settings.enable_pivot_debug_plot,
            "enable_path_debug_plots": settings.enable_path_debug_plots,
            "enable_execution_motion_trace": settings.enable_execution_motion_trace,
            "execution_motion_trace_sample_period_s": settings.execution_motion_trace_sample_period_s,
        }

    @staticmethod
    def from_flat_dict(flat: dict, base: PaintProcessConfig) -> PaintProcessConfig:
        pickup = replace(
            base.pickup_motion,
            approach_offset_mm=float(flat.get("pickup_approach_offset_mm", base.pickup_motion.approach_offset_mm)),
            contact_offset_mm=float(flat.get("pickup_contact_offset_mm", base.pickup_motion.contact_offset_mm)),
            initial_lift_clearance_mm=float(
                flat.get("pickup_initial_lift_clearance_mm", base.pickup_motion.initial_lift_clearance_mm)
            ),
            approach_vel_percent=float(flat.get("pickup_approach_vel_percent", base.pickup_motion.approach_vel_percent)),
            approach_acc_percent=float(flat.get("pickup_approach_acc_percent", base.pickup_motion.approach_acc_percent)),
            descend_vel_percent=float(flat.get("pickup_descend_vel_percent", base.pickup_motion.descend_vel_percent)),
            descend_acc_percent=float(flat.get("pickup_descend_acc_percent", base.pickup_motion.descend_acc_percent)),
            lift_align_vel_percent=float(flat.get("pickup_lift_align_vel_percent", base.pickup_motion.lift_align_vel_percent)),
            lift_align_acc_percent=float(flat.get("pickup_lift_align_acc_percent", base.pickup_motion.lift_align_acc_percent)),
            change_plane_vel_percent=float(
                flat.get("pickup_change_plane_vel_percent", base.pickup_motion.change_plane_vel_percent)
            ),
            change_plane_acc_percent=float(
                flat.get("pickup_change_plane_acc_percent", base.pickup_motion.change_plane_acc_percent)
            ),
            combine_change_plane_with_first_contact=bool(
                flat.get(
                    "combine_change_plane_with_first_contact",
                    base.pickup_motion.combine_change_plane_with_first_contact,
                )
            ),
            stage_transition_vel_percent=float(
                flat.get("pickup_stage_transition_vel_percent", base.pickup_motion.stage_transition_vel_percent)
            ),
            stage_transition_acc_percent=float(
                flat.get("pickup_stage_transition_acc_percent", base.pickup_motion.stage_transition_acc_percent)
            ),
            first_contact_vel_percent=float(
                flat.get("pickup_first_contact_vel_percent", base.pickup_motion.first_contact_vel_percent)
            ),
            first_contact_acc_percent=float(
                flat.get("pickup_first_contact_acc_percent", base.pickup_motion.first_contact_acc_percent)
            ),
        )
        cleanup = replace(
            base.edge_cleanup,
            enabled_after_xz_ry=bool(flat.get("cleanup_enabled_after_xz_ry", base.edge_cleanup.enabled_after_xz_ry)),
            enabled_after_xy_rz=bool(flat.get("cleanup_enabled_after_xy_rz", base.edge_cleanup.enabled_after_xy_rz)),
            enable_second_pass=bool(flat.get("cleanup_enable_second_pass", base.edge_cleanup.enable_second_pass)),
            vel_percent=float(flat.get("cleanup_vel_percent", base.edge_cleanup.vel_percent)),
            acc_percent=float(flat.get("cleanup_acc_percent", base.edge_cleanup.acc_percent)),
            spacing_mm=float(flat.get("cleanup_spacing_mm", base.edge_cleanup.spacing_mm)),
            z_offset_mm=float(flat.get("cleanup_z_offset_mm", base.edge_cleanup.z_offset_mm)),
            second_pass_pivot_z_offset_mm=float(
                flat.get("cleanup_second_pass_pivot_z_offset_mm", base.edge_cleanup.second_pass_pivot_z_offset_mm)
            ),
        )
        dropoff = replace(
            base.dropoff,
            strategy=str(flat.get("dropoff_strategy", base.dropoff.strategy)),
            release_align_vel_percent=float(
                flat.get("dropoff_release_align_vel_percent", base.dropoff.release_align_vel_percent)
            ),
            release_align_acc_percent=float(
                flat.get("dropoff_release_align_acc_percent", base.dropoff.release_align_acc_percent)
            ),
        )
        magazine = replace(
            base.magazine_load,
            enabled=bool(flat.get("magazine_load_enabled", base.magazine_load.enabled)),
            camera_settle_s=float(flat.get("magazine_camera_settle_s", base.magazine_load.camera_settle_s)),
            release_settle_s=float(flat.get("magazine_release_settle_s", base.magazine_load.release_settle_s)),
            move_to_magazine_vel_percent=float(
                flat.get(
                    "magazine_move_to_magazine_vel_percent",
                    base.magazine_load.move_to_magazine_vel_percent,
                )
            ),
            move_to_magazine_acc_percent=float(
                flat.get(
                    "magazine_move_to_magazine_acc_percent",
                    base.magazine_load.move_to_magazine_acc_percent,
                )
            ),
            transfer_to_calibration_vel_percent=float(
                flat.get(
                    "magazine_transfer_to_calibration_vel_percent",
                    base.magazine_load.transfer_to_calibration_vel_percent,
                )
            ),
            transfer_to_calibration_acc_percent=float(
                flat.get(
                    "magazine_transfer_to_calibration_acc_percent",
                    base.magazine_load.transfer_to_calibration_acc_percent,
                )
            ),
        )
        safe_travel = replace(
            base.safe_travel,
            enabled=bool(flat.get("safe_travel_enabled", base.safe_travel.enabled)),
            positions=PaintProcessSettingsMapper._waypoint_list_from_value(
                flat.get("safe_travel_positions", base.safe_travel.positions),
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
                flat.get("dropoff_safe_travel_positions", base.dropoff_safe_travel.positions),
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
                flat.get("nav_calibration_move_vel_percent", base.navigation_return.calibration_move_vel_percent)
            ),
            calibration_move_acc_percent=float(
                flat.get("nav_calibration_move_acc_percent", base.navigation_return.calibration_move_acc_percent)
            ),
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
