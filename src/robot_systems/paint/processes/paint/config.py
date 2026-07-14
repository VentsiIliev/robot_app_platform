from dataclasses import dataclass, field

from src.engine.robot.path_preparation import PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL, PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR


@dataclass(frozen=True)
class PickupMotionConfig:
    """Pickup/staging motion tuning.

    Values are robot velocity/acceleration percentages unless the suffix is ``_mm``.
    Each phase exposes its own ``vel_percent`` / ``acc_percent`` pair so cycle-time
    tuning can be done without changing the pickup sequence.
    """

    # Heights and clearances.
    default_z_mm: float = 300.0
    approach_offset_mm: float = 100.0
    contact_offset_mm: float = 2.0
    initial_lift_clearance_mm: float = 20.0

    # Fallback motion used by generic pickup helper calls.
    default_vel_percent: float = 20.0
    default_acc_percent: float = 50.0

    # Move from the current robot pose to the pickup approach pose.
    approach_vel_percent: float = 30.0
    approach_acc_percent: float = 50.0

    # Controlled final descent from approach height to pickup contact.
    descend_vel_percent: float = 60.0
    descend_acc_percent: float = 40.0

    # Lift away from pickup contact, then align to the paint start orientation.
    lift_align_vel_percent: float = 80.0
    lift_align_acc_percent: float = 30.0

    # Change from pickup/table plane orientation to paint plane orientation.
    change_plane_vel_percent: float = 50.0
    change_plane_acc_percent: float = 20.0
    # Combine change-plane orientation with the first pivot-contact translation.
    combine_change_plane_with_first_contact: bool = True

    # Optional intermediate staging poses between change-plane and pivot contact.
    stage_transition_vel_percent: float = 50.0
    stage_transition_acc_percent: float = 20.0

    # Move into the first pivot contact pose.
    first_contact_vel_percent: float = 50.0
    first_contact_acc_percent: float = 20.0

    # XY/RZ edge-cleanup motion after XZ/RY paint; separate from paint and unwind speeds.
    edge_cleanup_vel_percent: float = 50.0
    edge_cleanup_acc_percent: float = 30.0
    # Cleanup uses the prepared contour; approach/retreat transitions use this spacing.
    edge_cleanup_spacing_mm: float = 3.0
    # Cleanup-only Z adjustment in robot coordinates. Negative lowers into the belt.
    edge_cleanup_z_offset_mm: float = 0.0
    # ROS reachability validation costs ~2s per cleanup transition; enable only when commissioning.
    edge_cleanup_validate_transition_poses: bool = False

    # Deprecated: pickup orientation is no longer restored before release.
    restore_orientation_z_lift_mm: float = 0.0

    # Return from pivot completion back to the pickup align pose before release.
    release_align_vel_percent: float = 50.0
    release_align_acc_percent: float = 20.0

    # Deprecated: pickup orientation is no longer restored before vacuum release.
    release_restore_vel_percent: float = 50.0
    release_restore_acc_percent: float = 30.0


@dataclass(frozen=True)
class PaintNavigationReturnConfig:
    """Navigation-return motion tuning for paint-system cleanup moves."""

    # Joint-6 unwind velocity percentage sent to the ROS2 /unwind/joint6 endpoint.
    unwind_vel_percent: float = 50.0
    # Joint-6 unwind acceleration percentage sent to the ROS2 /unwind/joint6 endpoint.
    unwind_acc_percent: float = 20.0
    # Queue the unwind request if ROS2 is still finishing the previous motion.
    unwind_queue_if_busy: bool = True
    # Move from the post-unwind pose back to the calibration movement group pose.
    calibration_move_vel_percent: float = 30.0
    calibration_move_acc_percent: float = 40.0


@dataclass(frozen=True)
class PaintProjectionTuning:
    """Numeric tuning values for projected paint-path geometry."""
    smooth_max_linear_step_mm: float = 1.0
    smooth_max_angular_step_deg: float = 1.0
    rotation_deadband_deg: float = 0.5


@dataclass(frozen=True)
class PaintMotionPlaneSpec:
    """Axis and orientation mapping for one supported paint motion plane."""
    planar_axes: tuple[str, str]
    source_planar_coordinate_indices: tuple[int, int]
    planar_coordinate_indices: tuple[int, int]
    orthogonal_position_index: int
    rotation_index: int
    orientation_overrides_deg: dict[str, float] = field(default_factory=dict)
    contact_heading_offset_deg: float = 180.0
    axis_offsets_deg: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class PaintProjectionRules:
    """Projection-time domain mappings used by `PaintSimulationConfig`."""
    motion_plane_specs: dict[str, PaintMotionPlaneSpec] = field(default_factory=lambda: {
        "xy_z_rz": PaintMotionPlaneSpec(
            planar_axes=("x", "y"),
            source_planar_coordinate_indices=(0, 1),
            planar_coordinate_indices=(0, 1),
            orthogonal_position_index=2,
            rotation_index=5,
            axis_offsets_deg={"x": 0.0, "y": 90.0},
        ),
        "xz_y_ry": PaintMotionPlaneSpec(
            planar_axes=("x", "z"),
            source_planar_coordinate_indices=(0, 1),
            planar_coordinate_indices=(0, 2),
            orthogonal_position_index=1,
            rotation_index=4,
            axis_offsets_deg={"x": 0.0, "z": 90.0},
        ),
    })
    side_signs: dict[str, float] = field(default_factory=lambda: {
        "positive": -1.0,
        "negative": 1.0,
    })
    translation_direction_signs: dict[str, float] = field(default_factory=lambda: {
        "forward": 1.0,
        "reverse": -1.0,
    })

    @property
    def default_motion_plane(self) -> str:
        return "xy_z_rz"

    @property
    def default_paint_side(self) -> str:
        return "negative"

    @property
    def default_translation_direction(self) -> str:
        return "forward"


PAINT_PROJECTION_RULES = PaintProjectionRules()
PAINT_PROJECTION_TUNING = PaintProjectionTuning()


@dataclass(frozen=True)
class PaintPivotProfile:
    """Derived low-level pivot settings consumed by the paint executor."""

    motion_plane: str
    translation_axis: str
    translation_direction: str
    paint_side: str
    mirror_execution_rotation: bool
    mirror_pickup_handoff: bool
    pickup_axis_alignment_sign: float


@dataclass(frozen=True)
class PaintProcessConfig:
    """Single source of truth for platform-side paint process behavior."""
    # Target point used when transforming contours and pickup points into robot coordinates.
    execution_target_point: str = "tool"
    # Apply the legacy camera-height Z compensation during pixel-to-mm conversion.
    enable_z_shift_pixel_compensation: bool = False
    # Controls whether contours are converted with raw PPM geometry or calibrated homography/residuals.
    # contour_pixel_to_mm_mode: str = PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL
    contour_pixel_to_mm_mode: str = PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR
    # Sample current robot poses during blocking paint trajectory execution and compare
    # them with the commanded path. Disabled by default because it polls the robot state.
    enable_execution_motion_trace: bool = False
    execution_motion_trace_sample_period_s: float = 0.05
    # Selects the active paint plane: "xz_y_ry" pivots in X/Z using robot RY; "xy_z_rz" paints in X/Y using RZ.
    pivot_motion_plane: str = "xz_y_ry"
    # pivot_motion_plane: str = "xy_z_rz"
    # Navigation group used for pickup/camera-table alignment poses.
    primary_group_id: str = "PAINTING"
    # Navigation group used as the paint/pivot reference pose for XZ/RY painting.
    secondary_group_id: str = "PAINTING_NEW"
    # Main pivot tuning knobs. The lower-level executor flags are derived from these.
    pivot_axis: str = "x"
    pivot_direction: str = "reverse"
    pivot_contact_side: str = "positive"
    mirror_xz_ry_execution_rotation_value: bool = True
    pickup_axis_alignment_sign_value: float = 1.0
    # When the active process paints in XZ/RY, run an XY/RZ edge-cleanup pass
    # before releasing the held workpiece. Disable for the original single-pass flow.
    enable_edge_cleanup_after_xz_ry: bool = False
    # Enables reachability sampling before executing XZ/RY pivot paths.
    enable_xz_ry_preflight: bool = False
    # Maximum number of sampled XZ/RY poses checked when preflight is enabled.
    xz_ry_preflight_max_checks: int = 0
    # Turns the vacuum pump on/off around pickup and release.
    enable_vacuum_pump: bool = True
    # Applies the configured camera-to-TCP pickup offset only for legacy camera-target pickup plans.
    apply_camera_to_tcp_for_pickup: bool = True
    # Pickup motion heights, speed, acceleration, and tool/user numbers.
    pickup_motion: PickupMotionConfig = field(default_factory=PickupMotionConfig)
    # Cleanup return motion used before moving back to calibration.
    navigation_return: PaintNavigationReturnConfig = field(default_factory=PaintNavigationReturnConfig)
    # Enables the matplotlib debug plot generated after pivot path computation.
    enable_pivot_debug_plot: bool = False

    @property
    def paint_base_group_id(self) -> str:
        """Return the navigation group used as the active paint base."""
        if self.pivot_motion_plane == "xz_y_ry":
            return self.secondary_group_id
        return self.primary_group_id

    @property
    def pickup_base_group_id(self) -> str:
        """Return the navigation group used for pickup/alignment."""
        return self.primary_group_id

    @property
    def pickup_axis_alignment_sign(self) -> float:
        """Return the pickup orientation ambiguity sign."""
        return -1.0 if float(self.pickup_axis_alignment_sign_value) < 0.0 else 1.0

    @property
    def pivot_side(self) -> str:
        """Return the default contour side used for the active paint plane."""
        side = str(self.pivot_contact_side or "positive").strip().lower()
        return side if side in PAINT_PROJECTION_RULES.side_signs else PAINT_PROJECTION_RULES.default_paint_side

    @property
    def pivot_translation_axis(self) -> str:
        """Deprecated compatibility alias for the derived pivot axis."""
        return str(self.pivot_axis or "x").strip().lower()

    @property
    def pivot_translation_direction(self) -> str:
        """Deprecated compatibility alias for the derived pivot travel direction."""
        direction = str(self.pivot_direction or "forward").strip().lower()
        if direction in {"positive", "+", "forward"}:
            return "forward"
        if direction in {"negative", "-", "reverse"}:
            return "reverse"
        return PAINT_PROJECTION_RULES.default_translation_direction

    @property
    def flip_xz_ry_execution_rotation_direction(self) -> bool:
        """Deprecated compatibility alias derived from the active motion plane."""
        return self.pivot_motion_plane == "xz_y_ry" and bool(self.mirror_xz_ry_execution_rotation_value)

    @property
    def mirror_xz_ry_pickup_handoff(self) -> bool:
        """Deprecated compatibility alias for pickup handoff mapping."""
        return False

    @property
    def flip_pickup_axis_alignment_direction(self) -> bool:
        """Deprecated compatibility alias for the pickup alignment sign."""
        return self.pickup_axis_alignment_sign < 0.0

    @property
    def pivot_profile(self) -> PaintPivotProfile:
        """Return the derived pivot profile consumed by application wiring."""
        return PaintPivotProfile(
            motion_plane=self.pivot_motion_plane,
            translation_axis=self.pivot_translation_axis,
            translation_direction=self.pivot_translation_direction,
            paint_side=self.pivot_side,
            mirror_execution_rotation=self.flip_xz_ry_execution_rotation_direction,
            mirror_pickup_handoff=self.mirror_xz_ry_pickup_handoff,
            pickup_axis_alignment_sign=self.pickup_axis_alignment_sign,
        )

    @property
    def pickup_default_z_mm(self) -> float:
        return float(self.pickup_motion.default_z_mm)

    @property
    def pickup_default_vel_percent(self) -> float:
        return float(self.pickup_motion.default_vel_percent)

    @property
    def pickup_default_acc_percent(self) -> float:
        return float(self.pickup_motion.default_acc_percent)

    @property
    def pickup_descend_vel_percent(self) -> float:
        return float(self.pickup_motion.descend_vel_percent)

    @property
    def pickup_descend_acc_percent(self) -> float:
        return float(self.pickup_motion.descend_acc_percent)

    @property
    def pickup_approach_vel_percent(self) -> float:
        return float(self.pickup_motion.approach_vel_percent)

    @property
    def pickup_approach_acc_percent(self) -> float:
        return float(self.pickup_motion.approach_acc_percent)

    @property
    def pickup_lift_align_vel_percent(self) -> float:
        return float(self.pickup_motion.lift_align_vel_percent)

    @property
    def pickup_lift_align_acc_percent(self) -> float:
        return float(self.pickup_motion.lift_align_acc_percent)

    @property
    def pickup_change_plane_vel_percent(self) -> float:
        return float(self.pickup_motion.change_plane_vel_percent)

    @property
    def pickup_change_plane_acc_percent(self) -> float:
        return float(self.pickup_motion.change_plane_acc_percent)

    @property
    def pickup_combine_change_plane_with_first_contact(self) -> bool:
        return bool(self.pickup_motion.combine_change_plane_with_first_contact)

    @property
    def pickup_stage_transition_vel_percent(self) -> float:
        return float(self.pickup_motion.stage_transition_vel_percent)

    @property
    def pickup_stage_transition_acc_percent(self) -> float:
        return float(self.pickup_motion.stage_transition_acc_percent)

    @property
    def pickup_first_contact_vel_percent(self) -> float:
        return float(self.pickup_motion.first_contact_vel_percent)

    @property
    def pickup_first_contact_acc_percent(self) -> float:
        return float(self.pickup_motion.first_contact_acc_percent)

    @property
    def pickup_edge_cleanup_vel_percent(self) -> float:
        return float(self.pickup_motion.edge_cleanup_vel_percent)

    @property
    def pickup_edge_cleanup_acc_percent(self) -> float:
        return float(self.pickup_motion.edge_cleanup_acc_percent)

    @property
    def pickup_edge_cleanup_spacing_mm(self) -> float:
        return float(self.pickup_motion.edge_cleanup_spacing_mm)

    @property
    def pickup_edge_cleanup_z_offset_mm(self) -> float:
        return float(self.pickup_motion.edge_cleanup_z_offset_mm)

    @property
    def pickup_edge_cleanup_validate_transition_poses(self) -> bool:
        return bool(self.pickup_motion.edge_cleanup_validate_transition_poses)

    @property
    def pickup_restore_orientation_z_lift_mm(self) -> float:
        return float(self.pickup_motion.restore_orientation_z_lift_mm)

    @property
    def pickup_release_align_vel_percent(self) -> float:
        return float(self.pickup_motion.release_align_vel_percent)

    @property
    def pickup_release_align_acc_percent(self) -> float:
        return float(self.pickup_motion.release_align_acc_percent)

    @property
    def pickup_release_restore_vel_percent(self) -> float:
        return float(self.pickup_motion.release_restore_vel_percent)

    @property
    def pickup_release_restore_acc_percent(self) -> float:
        return float(self.pickup_motion.release_restore_acc_percent)

    @property
    def pickup_approach_offset_mm(self) -> float:
        return float(self.pickup_motion.approach_offset_mm)

    @property
    def pickup_contact_offset_mm(self) -> float:
        return float(self.pickup_motion.contact_offset_mm)

    @property
    def pickup_initial_lift_clearance_mm(self) -> float:
        return float(self.pickup_motion.initial_lift_clearance_mm)

    @property
    def navigation_unwind_vel_percent(self) -> float:
        return float(self.navigation_return.unwind_vel_percent)

    @property
    def navigation_unwind_acc_percent(self) -> float:
        return float(self.navigation_return.unwind_acc_percent)

    @property
    def navigation_unwind_queue_if_busy(self) -> bool:
        return bool(self.navigation_return.unwind_queue_if_busy)

    @property
    def navigation_calibration_move_vel_percent(self) -> float:
        return float(self.navigation_return.calibration_move_vel_percent)

    @property
    def navigation_calibration_move_acc_percent(self) -> float:
        return float(self.navigation_return.calibration_move_acc_percent)


PAINT_PROCESS_CONFIG = PaintProcessConfig()

@dataclass(frozen=True)
class PaintSimulationConfig:
    """Normalized settings that control projected paint motion geometry."""
    motion_plane: str = "xy_z_rz"
    translation_axis: str = "x"
    paint_side: str = "negative"
    translation_direction: str = "reverse"
    apply_camera_to_tcp_for_pickup: bool = False
    camera_to_tcp_x_offset: float = 0.0
    camera_to_tcp_y_offset: float = 0.0
    rotation_direction_sign: float = 1.0

    @property
    def rules(self) -> PaintProjectionRules:
        """Return the shared projection rules for all supported paint planes."""
        return PAINT_PROJECTION_RULES

    @property
    def plane_spec(self) -> PaintMotionPlaneSpec:
        """Return the axis/index mapping for the selected motion plane."""
        return self.rules.motion_plane_specs[self.motion_plane]

    @property
    def planar_axes(self) -> tuple[str, str]:
        """Return the coordinate names that span the active 2D motion plane."""
        return tuple(self.plane_spec.planar_axes)

    @property
    def planar_coordinate_indices(self) -> tuple[int, int]:
        """Return the robot pose indices used as planar coordinates."""
        return tuple(self.plane_spec.planar_coordinate_indices)

    @property
    def source_planar_coordinate_indices(self) -> tuple[int, int]:
        """Return the source path indices used to derive 2D contour geometry."""
        return tuple(self.plane_spec.source_planar_coordinate_indices)

    @property
    def orthogonal_position_index(self) -> int:
        """Return the fixed position component outside the active motion plane."""
        return int(self.plane_spec.orthogonal_position_index)

    @property
    def rotation_index(self) -> int:
        """Return the orientation component rotated while projecting paint motion."""
        return int(self.plane_spec.rotation_index)

    @property
    def orientation_overrides_deg(self) -> dict[str, float]:
        """Return any fixed orientation overrides for process poses in the active plane."""
        return dict(self.plane_spec.orientation_overrides_deg)

    @property
    def contact_heading_offset_deg(self) -> float:
        """Return the in-plane heading offset used for the first contact alignment."""
        return float(self.plane_spec.contact_heading_offset_deg)

    @property
    def valid_translation_axes(self) -> tuple[str, ...]:
        """Return the translation-axis names valid for the selected motion plane."""
        return tuple(self.plane_spec.axis_offsets_deg.keys())

    @property
    def paint_axis_offset_deg(self) -> float:
        """Return the heading offset for the selected translation axis in the active plane."""
        return float(self.plane_spec.axis_offsets_deg[self.translation_axis])

    @property
    def side_sign(self) -> float:
        """Return the signed multiplier for which side of the paint path to use."""
        return self.rules.side_signs[self.paint_side]

    @property
    def direction_sign(self) -> float:
        """Return the signed multiplier for forward vs reverse projected travel."""
        return self.rules.translation_direction_signs[self.translation_direction]
