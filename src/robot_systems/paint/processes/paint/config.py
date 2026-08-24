from dataclasses import dataclass, field

from src.engine.robot.path_preparation import PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL, PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR

PICKUP_CONTACT_MODE_PLANNED = "planned"
PICKUP_CONTACT_MODE_SERVO_CONTACT = "servo_contact"
PICKUP_CONTACT_MODE_HEIGHT_MEASURE = "height_measure"
PICKUP_CONTACT_MODES = (
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
    PICKUP_CONTACT_MODE_HEIGHT_MEASURE,
)


# [LIVE SETTINGS] marks defaults that are already read through the paint-process
# settings service at runtime. Unmarked values are still static defaults or need
# separate wiring before UI changes can affect the running paint process.


@dataclass(frozen=True)
class PickupMotionConfig:
    """Pickup/staging motion tuning.

    Values are robot velocity/acceleration percentages unless the suffix is ``_mm``.
    Each phase exposes its own ``vel_percent`` / ``acc_percent`` pair so cycle-time
    tuning can be done without changing the pickup sequence.
    """

    # Heights and clearances.
    approach_offset_mm: float = 100.0  # [LIVE SETTINGS]
    contact_offset_mm: float = 5.0  # [LIVE SETTINGS]
    initial_lift_clearance_mm: float = 20.0  # [LIVE SETTINGS]

    # Move from the current robot pose to the pickup approach pose.
    approach_vel_percent: float = 60.0  # [LIVE SETTINGS]
    approach_acc_percent: float = 50.0  # [LIVE SETTINGS]
    approach_motion_type: str = "ptp"  # [LIVE SETTINGS]
    approach_blendR: float = 20.0  # [LIVE SETTINGS]

    # Controlled final descent from approach height to pickup contact.
    descend_vel_percent: float = 60.0  # [LIVE SETTINGS]
    descend_acc_percent: float = 40.0  # [LIVE SETTINGS]
    descend_motion_type: str = "linear"  # [LIVE SETTINGS]
    descend_blendR: float = 0.0  # [LIVE SETTINGS]

    # Lift away from pickup contact, then align to the paint start orientation.
    lift_align_vel_percent: float = 80.0  # [LIVE SETTINGS]
    lift_align_acc_percent: float = 40.0  # [LIVE SETTINGS]
    lift_align_motion_type: str = "ptp"  # [LIVE SETTINGS]
    lift_align_blendR: float = 20.0  # [LIVE SETTINGS]

    # Change from pickup/table plane orientation to paint plane orientation.
    change_plane_vel_percent: float = 80.0  # [LIVE SETTINGS]
    change_plane_acc_percent: float = 40.0  # [LIVE SETTINGS]
    change_plane_motion_type: str = "ptp"  # [LIVE SETTINGS]
    change_plane_blendR: float = 20.0  # [LIVE SETTINGS]
    # Combine change-plane orientation with the first pivot-contact translation.
    combine_change_plane_with_first_contact: bool = True

    # Optional intermediate staging poses between change-plane and pivot contact.
    stage_transition_vel_percent: float = 50.0  # [LIVE SETTINGS]
    stage_transition_acc_percent: float = 20.0  # [LIVE SETTINGS]
    stage_transition_motion_type: str = "ptp"  # [LIVE SETTINGS]
    stage_transition_blendR: float = 20.0  # [LIVE SETTINGS]

    # Move into the first pivot contact pose.
    first_contact_vel_percent: float = 80.0  # [LIVE SETTINGS]
    first_contact_acc_percent: float = 30.0  # [LIVE SETTINGS]
    first_contact_motion_type: str = "ptp"  # [LIVE SETTINGS]
    first_contact_blendR: float = 0.0  # [LIVE SETTINGS]

    # Pickup contact strategy. Defaults preserve the fully planned
    # approach/descend/lift sequence. Valid values: planned | servo_contact | height_measure.
    pickup_contact_mode: str = PICKUP_CONTACT_MODE_PLANNED  # [LIVE SETTINGS]
    magazine_pickup_contact_mode: str = PICKUP_CONTACT_MODE_PLANNED  # [LIVE SETTINGS]
    servo_contact_linear_mm_s: float = 10.0  # [LIVE SETTINGS]
    servo_contact_retract_distance_mm: float = 10.0  # [LIVE SETTINGS]
    servo_contact_retract_linear_mm_s: float = 25.0  # [LIVE SETTINGS]
    servo_contact_timeout_s: float = 5.0  # [LIVE SETTINGS]
    servo_contact_poll_interval_s: float = 0.02  # [LIVE SETTINGS]
    servo_contact_preflight_read_attempts: int = 2  # [LIVE SETTINGS]
    servo_contact_read_failure_limit: int = 3  # [LIVE SETTINGS]
    servo_contact_fallback_to_planned_descend: bool = False  # [LIVE SETTINGS]
    servo_contact_dummy_sensor_enabled: bool = False  # [LIVE SETTINGS]
    servo_contact_dummy_detect_after_s: float = 1.0  # [LIVE SETTINGS]

@dataclass(frozen=True)
class PaintEdgeCleanupConfig:
    """Optional XY/RZ cleanup pass tuning used after XZ/RY paint."""

    # Run an XY/RZ edge-cleanup pass before releasing the held workpiece.
    enabled_after_xz_ry: bool = False  # [LIVE SETTINGS]
    # Run an XY/RZ edge-cleanup pass after XY/RZ paint, reprojected at the cleanup station.
    enabled_after_xy_rz: bool = False  # [LIVE SETTINGS]
    # Replay the cleanup path in reverse with an additional paint-axis/base Z offset.
    enable_second_pass: bool = False  # [LIVE SETTINGS]
    # XY/RZ cleanup motion after XZ/RY paint; separate from paint and unwind speeds.
    vel_percent: float = 80.0  # [LIVE SETTINGS]
    acc_percent: float = 60.0  # [LIVE SETTINGS]
    motion_type: str = "linear"  # [LIVE SETTINGS]
    blendR: float = 0.0  # [LIVE SETTINGS]
    # Cleanup uses the prepared contour; approach/retreat transitions use this spacing.
    spacing_mm: float = 3.0  # [LIVE SETTINGS]
    # Cleanup-only Z adjustment in robot coordinates. Negative lowers into the belt.
    z_offset_mm: float = 0.0  # [LIVE SETTINGS]
    # Additional paint-axis/base Z offset for the optional second cleanup pass.
    second_pass_pivot_z_offset_mm: float = -15.0  # [LIVE SETTINGS] 20mm below the belt !


@dataclass(frozen=True)
class PaintDropoffConfig:
    """Dropoff/release motion tuning after paint and Joint 6 unwind."""

    # Return from pivot completion back to the pickup align pose before release.
    strategy: str = "pickup_origin"
    release_align_vel_percent: float = 60.0  # [LIVE SETTINGS]
    release_align_acc_percent: float = 40.0  # [LIVE SETTINGS]
    release_align_motion_type: str = "ptp"  # [LIVE SETTINGS]
    release_align_blendR: float = 0.0  # [LIVE SETTINGS]


@dataclass(frozen=True)
class PaintMagazineLoadConfig:
    """Optional pre-run transfer from magazine capture station to calibration table."""

    enabled: bool = False  # [LIVE SETTINGS]
    magazine_group_id: str = "Magazine"
    calibration_group_id: str = "CALIBRATION"
    move_to_magazine_vel_percent: float = 30.0  # [LIVE SETTINGS]
    move_to_magazine_acc_percent: float = 30.0  # [LIVE SETTINGS]
    move_to_magazine_motion_type: str = "ptp"  # [LIVE SETTINGS]
    move_to_magazine_blendR: float = 0.0  # [LIVE SETTINGS]
    transfer_to_calibration_vel_percent: float = 30.0  # [LIVE SETTINGS]
    transfer_to_calibration_acc_percent: float = 30.0  # [LIVE SETTINGS]
    transfer_to_calibration_motion_type: str = "ptp"  # [LIVE SETTINGS]
    transfer_to_calibration_blendR: float = 0.0  # [LIVE SETTINGS]
    release_z_mm: float = 50.0  # [LIVE SETTINGS]
    camera_settle_s: float = 0.5
    release_settle_s: float = 0.5


@dataclass(frozen=True)
class PaintSafeTravelConfig:
    """Optional safe waypoints used while carrying the workpiece from calibration to paint."""

    enabled: bool = False  # [LIVE SETTINGS]
    position: list[float] = field(default_factory=list)
    positions: list[object] = field(default_factory=list)
    movement_group_id: str = ""


@dataclass(frozen=True)
class PaintToDropoffSafeTravelConfig:
    """Optional safe waypoints used while carrying the workpiece from paint to dropoff."""

    enabled: bool = False  # [LIVE SETTINGS]
    position: list[float] = field(default_factory=list)
    positions: list[object] = field(default_factory=list)


@dataclass(frozen=True)
class PaintNavigationReturnConfig:
    """Navigation-return motion tuning for paint-system cleanup moves."""

    # Joint-6 unwind velocity percentage sent to the ROS2 /unwind/joint6 endpoint.
    unwind_vel_percent: float = 100.0  # [LIVE SETTINGS]
    # Joint-6 unwind acceleration percentage sent to the ROS2 /unwind/joint6 endpoint.
    unwind_acc_percent: float = 60.0  # [LIVE SETTINGS]
    # Queue the unwind request if ROS2 is still finishing the previous motion.
    unwind_queue_if_busy: bool = True
    # Explicit navigation move to the calibration movement group pose.
    calibration_move_vel_percent: float = 30.0  # [LIVE SETTINGS]
    calibration_move_acc_percent: float = 40.0  # [LIVE SETTINGS]
    calibration_move_motion_type: str = "ptp"  # [LIVE SETTINGS]
    calibration_move_blendR: float = 0.0  # [LIVE SETTINGS]


@dataclass(frozen=True)
class PaintInterpolationConfig:
    """Path-heading interpolation tuning for paint contour preparation."""

    # Lookahead distance used when deriving per-point RZ from the path tangent.
    path_tangent_lookahead_mm: float = 15.0  # [LIVE SETTINGS]
    # Ignore smaller tangent heading changes when rebuilding path RZ.
    path_tangent_deadband_deg: float = 5.0  # [LIVE SETTINGS]


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

    default_motion_plane: str = "xy_z_rz"
    default_paint_side: str = "negative"
    default_translation_direction: str = "forward"


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
    # Apply the legacy camera-height Z compensation during pixel-to-mm conversion.
    enable_z_shift_pixel_compensation: bool = False
    # Controls whether contours are converted with raw PPM geometry or calibrated homography/residuals.
    # contour_pixel_to_mm_mode: str = PIXEL_TO_MM_MODE_HOMOGRAPHY_RESIDUAL
    contour_pixel_to_mm_mode: str = PIXEL_TO_MM_MODE_GEOMETRY_PPM_ANCHOR
    # Sample current robot poses during blocking paint trajectory execution and compare
    # them with the commanded path. Disabled by default because it polls the robot state.
    enable_execution_motion_trace: bool = False  # [LIVE SETTINGS]
    execution_motion_trace_sample_period_s: float = 0.05  # [LIVE SETTINGS]
    # Selects the active paint plane: "xz_y_ry" pivots in X/Z using robot RY; "xy_z_rz" paints in X/Y using RZ.
    pivot_motion_plane: str = "xz_y_ry"
    # pivot_motion_plane: str = "xy_z_rz"
    # Navigation group used as the paint/pivot reference pose for XY/RZ painting.
    primary_group_id: str = "Vertical Shaft"
    # Navigation group used as the paint/pivot reference pose for XZ/RY painting.
    secondary_group_id: str = "Horizontal Shaft"
    # Navigation group used as the XY/RZ reference pose for the post-paint cleanup pass.
    cleanup_group_id: str = "Clean"
    # Main pivot tuning knobs. The lower-level executor flags are derived from these.
    pivot_axis: str = "x"
    pivot_direction: str = "reverse"
    pivot_contact_side: str = "positive"
    mirror_xz_ry_execution_rotation_value: bool = True
    pickup_axis_alignment_sign_value: float = 1.0
    # Turns the vacuum pump on/off around pickup and release.
    enable_vacuum_pump: bool = True
    # Repeat production cycles until the active source no longer yields a workpiece.
    run_while_workpiece_found: bool = True  # [LIVE SETTINGS]
    # Match the captured contour against the saved workpiece library. When disabled,
    # execute the captured contour directly with the default process settings.
    enable_workpiece_matching: bool = True  # [LIVE SETTINGS]
    default_paint_velocity_percent: float = 10.0  # [LIVE SETTINGS]
    default_paint_acceleration_percent: float = 10.0  # [LIVE SETTINGS]
    # Log one end-of-cycle timing table for every paint execution state.
    enable_execution_state_timing: bool = True  # [LIVE SETTINGS]
    # Freeze the paint dashboard preview on the calibration-area capture while the paint cycle runs.
    pause_dashboard_live_view_after_capture: bool = True  # [LIVE SETTINGS]
    # Applies the configured camera-to-TCP pickup offset only for legacy camera-target pickup plans.
    apply_camera_to_tcp_for_pickup: bool = True
    # Pickup motion heights, speed, acceleration, and tool/user numbers.
    pickup_motion: PickupMotionConfig = field(default_factory=PickupMotionConfig)
    # Optional XY/RZ cleanup pass tuning.
    edge_cleanup: PaintEdgeCleanupConfig = field(default_factory=PaintEdgeCleanupConfig)
    # Dropoff/release motion tuning.
    dropoff: PaintDropoffConfig = field(default_factory=PaintDropoffConfig)
    # Optional magazine pickup before the normal paint run.
    magazine_load: PaintMagazineLoadConfig = field(default_factory=PaintMagazineLoadConfig)
    # Optional carried-workpiece waypoint before entering the paint contact area.
    safe_travel: PaintSafeTravelConfig = field(default_factory=PaintSafeTravelConfig)
    # Optional carried-workpiece waypoint before entering the dropoff area.
    dropoff_safe_travel: PaintToDropoffSafeTravelConfig = field(default_factory=PaintToDropoffSafeTravelConfig)
    # Cleanup return motion used before moving back to calibration.
    navigation_return: PaintNavigationReturnConfig = field(default_factory=PaintNavigationReturnConfig)
    # Interpolation and heading reconstruction tuning.
    interpolation: PaintInterpolationConfig = field(default_factory=PaintInterpolationConfig)
    # Enables the matplotlib debug plot generated after pivot path computation.
    enable_pivot_debug_plot: bool = False  # [LIVE SETTINGS]
    # Enables path-preparation diagnostic plots such as contour canonicalization and trajectory comparison.
    enable_path_debug_plots: bool = False  # [LIVE SETTINGS]



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

    rules: PaintProjectionRules = field(init=False, repr=False)
    plane_spec: PaintMotionPlaneSpec = field(init=False, repr=False)
    planar_axes: tuple[str, str] = field(init=False)
    planar_coordinate_indices: tuple[int, int] = field(init=False)
    source_planar_coordinate_indices: tuple[int, int] = field(init=False)
    orthogonal_position_index: int = field(init=False)
    rotation_index: int = field(init=False)
    orientation_overrides_deg: dict[str, float] = field(init=False)
    valid_translation_axes: tuple[str, ...] = field(init=False)
    paint_axis_offset_deg: float = field(init=False)
    side_sign: float = field(init=False)
    direction_sign: float = field(init=False)

    def __post_init__(self) -> None:
        rules = PAINT_PROJECTION_RULES
        plane_spec = rules.motion_plane_specs[self.motion_plane]
        object.__setattr__(self, "rules", rules)
        object.__setattr__(self, "plane_spec", plane_spec)
        object.__setattr__(self, "planar_axes", tuple(plane_spec.planar_axes))
        object.__setattr__(self, "planar_coordinate_indices", tuple(plane_spec.planar_coordinate_indices))
        object.__setattr__(self, "source_planar_coordinate_indices", tuple(plane_spec.source_planar_coordinate_indices))
        object.__setattr__(self, "orthogonal_position_index", int(plane_spec.orthogonal_position_index))
        object.__setattr__(self, "rotation_index", int(plane_spec.rotation_index))
        object.__setattr__(self, "orientation_overrides_deg", dict(plane_spec.orientation_overrides_deg))
        object.__setattr__(self, "valid_translation_axes", tuple(plane_spec.axis_offsets_deg.keys()))
        object.__setattr__(self, "paint_axis_offset_deg", float(plane_spec.axis_offsets_deg[self.translation_axis]))
        object.__setattr__(self, "side_sign", float(rules.side_signs[self.paint_side]))
        object.__setattr__(self, "direction_sign", float(rules.translation_direction_signs[self.translation_direction]))
