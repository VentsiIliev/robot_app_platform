from dataclasses import dataclass, field

from src.robot_systems.paint.processes.paint.align import (
    DXF_ALIGNMENT_STRATEGY_RIGID,
)


@dataclass(frozen=True)
class PickupMotionConfig:
    """Pickup-specific motion defaults shared by paint execution flows."""
    default_z_mm: float = 300.0
    default_vel_percent: float = 30.0
    default_acc_percent: float = 100.0
    approach_offset_mm: float = 100.0
    contact_offset_mm: float = 2.0


@dataclass(frozen=True)
class PaintProjectionTuning:
    """Numeric tuning values for projected paint-path geometry."""
    smooth_max_linear_step_mm: float = 1.0
    smooth_max_angular_step_deg: float = 0.2
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
            orientation_overrides_deg={"rx": 90.0},
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
class PaintProcessConfig:
    """Single source of truth for platform-side paint process behavior."""
    execution_target_point: str = "tool"
    enable_z_shift_pixel_compensation: bool = False
    dxf_alignment_strategy: str = DXF_ALIGNMENT_STRATEGY_RIGID
    dxf_max_scale_deviation: float = 0.03
    pivot_motion_plane: str = "xz_y_ry"
    primary_group_id: str = "PAINTING"
    secondary_group_id: str = "PAINTING_NEW"
    pivot_translation_axis: str = "x"
    pivot_translation_direction: str = "forward"
    flip_xz_ry_execution_rotation_direction: bool = True
    enable_xz_ry_preflight: bool = False
    xz_ry_preflight_max_checks: int = 8
    enable_vacuum_pump: bool = True
    apply_camera_to_tcp_for_pickup: bool = True
    pickup_motion: PickupMotionConfig = field(default_factory=PickupMotionConfig)

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
    def pivot_side(self) -> str:
        """Return the default contour side used for the active paint plane."""
        if self.pivot_motion_plane == "xz_y_ry":
            return "positive"
        return "negative"

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
    def pickup_approach_offset_mm(self) -> float:
        return float(self.pickup_motion.approach_offset_mm)

    @property
    def pickup_contact_offset_mm(self) -> float:
        return float(self.pickup_motion.contact_offset_mm)


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
