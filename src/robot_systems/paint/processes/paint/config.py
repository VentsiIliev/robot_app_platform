from dataclasses import dataclass

from src.robot_systems.paint.processes.paint.workpiece_alignment import (
    DXF_ALIGNMENT_STRATEGY_RIGID,
)

_PAINT_SMOOTH_MAX_LINEAR_STEP_MM = 1.0
_PAINT_SMOOTH_MAX_ANGULAR_STEP_DEG = 0.2
_PAINT_ROTATION_DEADBAND_DEG = 0.5
_PICKUP_DEFAULT_Z_MM = 300.0
_PICKUP_DEFAULT_VEL_PERCENT = 30.0
_PICKUP_DEFAULT_ACC_PERCENT = 100.0
_PICKUP_APPROACH_OFFSET_MM = 100.0
_PICKUP_CONTACT_OFFSET_MM = 2.0
_PAINT_MOTION_PLANE_SPECS = {
    "xy_z_rz": {
        "planar_axes": ("x", "y"),
        "source_planar_coordinate_indices": (0, 1),
        "planar_coordinate_indices": (0, 1),
        "orthogonal_position_index": 2,
        "rotation_index": 5,
        "orientation_overrides_deg": {},
        "contact_heading_offset_deg": 180.0,
        "axis_offsets_deg": {
            "x": 0.0,
            "y": 90.0,
        },
    },
    "xz_y_ry": {
        "planar_axes": ("x", "z"),
        "source_planar_coordinate_indices": (0, 1),
        "planar_coordinate_indices": (0, 2),
        "orthogonal_position_index": 1,
        "rotation_index": 4,
        "orientation_overrides_deg": {
            "rx": 90.0,
        },
        "contact_heading_offset_deg": 180.0,
        "axis_offsets_deg": {
            "x": 0.0,
            "z": 90.0,
        },
    },
}
_PAINT_SIDE_SIGNS = {
    "positive": -1.0,
    "negative": 1.0,
}
_PAINT_TRANSLATION_DIRECTION_SIGNS = {
    "forward": 1.0,
    "reverse": -1.0,
}


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
    pickup_default_z_mm: float = _PICKUP_DEFAULT_Z_MM
    pickup_default_vel_percent: float = _PICKUP_DEFAULT_VEL_PERCENT
    pickup_default_acc_percent: float = _PICKUP_DEFAULT_ACC_PERCENT
    pickup_approach_offset_mm: float = _PICKUP_APPROACH_OFFSET_MM
    pickup_contact_offset_mm: float = _PICKUP_CONTACT_OFFSET_MM

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
    def plane_spec(self) -> dict:
        """Return the axis/index mapping for the selected motion plane."""
        return _PAINT_MOTION_PLANE_SPECS[self.motion_plane]

    @property
    def planar_axes(self) -> tuple[str, str]:
        """Return the coordinate names that span the active 2D motion plane."""
        return tuple(self.plane_spec["planar_axes"])

    @property
    def planar_coordinate_indices(self) -> tuple[int, int]:
        """Return the robot pose indices used as planar coordinates."""
        return tuple(self.plane_spec["planar_coordinate_indices"])

    @property
    def source_planar_coordinate_indices(self) -> tuple[int, int]:
        """Return the source path indices used to derive 2D contour geometry."""
        return tuple(self.plane_spec["source_planar_coordinate_indices"])

    @property
    def orthogonal_position_index(self) -> int:
        """Return the fixed position component outside the active motion plane."""
        return int(self.plane_spec["orthogonal_position_index"])

    @property
    def rotation_index(self) -> int:
        """Return the orientation component rotated while projecting paint motion."""
        return int(self.plane_spec["rotation_index"])

    @property
    def orientation_overrides_deg(self) -> dict[str, float]:
        """Return any fixed orientation overrides for process poses in the active plane."""
        return dict(self.plane_spec.get("orientation_overrides_deg", {}))

    @property
    def contact_heading_offset_deg(self) -> float:
        """Return the in-plane heading offset used for the first contact alignment."""
        return float(self.plane_spec.get("contact_heading_offset_deg", 180.0))

    @property
    def valid_translation_axes(self) -> tuple[str, ...]:
        """Return the translation-axis names valid for the selected motion plane."""
        return tuple(self.plane_spec["axis_offsets_deg"].keys())

    @property
    def paint_axis_offset_deg(self) -> float:
        """Return the heading offset for the selected translation axis in the active plane."""
        return float(self.plane_spec["axis_offsets_deg"][self.translation_axis])

    @property
    def side_sign(self) -> float:
        """Return the signed multiplier for which side of the paint path to use."""
        return _PAINT_SIDE_SIGNS[self.paint_side]

    @property
    def direction_sign(self) -> float:
        """Return the signed multiplier for forward vs reverse projected travel."""
        return _PAINT_TRANSLATION_DIRECTION_SIGNS[self.translation_direction]
