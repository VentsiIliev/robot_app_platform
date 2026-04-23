from dataclasses import dataclass

_PIVOT_SMOOTH_MAX_LINEAR_STEP_MM = 1.0
_PIVOT_SMOOTH_MAX_ANGULAR_STEP_DEG = 0.2
_PIVOT_ROTATION_DEADBAND_DEG = 0.5
_PICKUP_DEFAULT_Z_MM = 300.0
_PICKUP_DEFAULT_VEL_PERCENT = 20.0
_PICKUP_DEFAULT_ACC_PERCENT = 20.0
_PICKUP_APPROACH_OFFSET_MM = 30.0
_PICKUP_CONTACT_OFFSET_MM = 2.0
_PIVOT_TRANSLATION_AXIS_OFFSETS_DEG = {
    "x": 0.0,
    "y": 90.0,
}
_PIVOT_SIDE_SIGNS = {
    "positive": 1.0,
    "negative": -1.0,
}
_PIVOT_TRANSLATION_DIRECTION_SIGNS = {
    "forward": 1.0,
    "reverse": -1.0,
}

@dataclass(frozen=True)
class PivotSimulationConfig:
    """Normalized settings that control projected pivot motion geometry."""
    translation_axis: str = "x"
    pivot_side: str = "negative"
    translation_direction: str = "forward"
    apply_camera_to_tcp_for_pickup: bool = False
    camera_to_tcp_x_offset: float = 0.0
    camera_to_tcp_y_offset: float = 0.0

    @property
    def paint_axis_offset_deg(self) -> float:
        """Return the heading offset that maps the selected translation axis to world RZ."""
        return _PIVOT_TRANSLATION_AXIS_OFFSETS_DEG[self.translation_axis]

    @property
    def side_sign(self) -> float:
        """Return the signed multiplier for which side of the pivot path to use."""
        return _PIVOT_SIDE_SIGNS[self.pivot_side]

    @property
    def direction_sign(self) -> float:
        """Return the signed multiplier for forward vs reverse projected travel."""
        return _PIVOT_TRANSLATION_DIRECTION_SIGNS[self.translation_direction]
