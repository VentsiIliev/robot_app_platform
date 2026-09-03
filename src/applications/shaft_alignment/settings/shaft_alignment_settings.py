from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ShaftAlignmentSettings:
    marker_id: int = 2
    marker_size_mm: float = 11.0
    point_of_interest_x_offset_mm: float = 2.12
    point_of_interest_y_offset_mm: float = 11.44
    minimum_area_px2: float = 0.0
    active_work_area: str = "vertical_shaft_alignment"
    raw_mode: bool = False
    orientation_strategy: str = "compare"
    orientation_primary_strategy: str = "corner_edge"
    calibration_pose: tuple[float, ...] = (-29.075, 217.269, 200.076, -179.99, 0.0, 0.0)
    capture_pose: tuple[float, ...] = (257.75, 215.7, 400.1, -179.2, 0.0, 0.0)
    base_region_width_px: int = 100
    base_region_height_px: int = 700
    tracking_region_padding_px: int = 50
    tracking_region_minimum_width_px: int = 160
    tracking_region_minimum_height_px: int = 160
    tracking_recovery_expansion_px: int = 50
    marker_misses_before_region_fallback: int = 10
    detections_before_tracking: int = 1
    acquisition_misses_before_reset: int = 3
    tracking_position_filter_alpha: float = 0.5
    tracking_prediction_gain: float = 0.5
    tracking_maximum_center_jump_px: float = 100.0
    tracking_maximum_area_ratio_change: float = 3.0
    stability_required_samples: int = 5
    stability_maximum_center_spread_px: float = 5.0
    stability_maximum_orientation_spread_deg: float = 3.0
    stability_misses_before_reset: int = 3
    reference_capture_samples: int = 30
    alignment_check_samples: int = 10
    misalignment_dx_threshold_mm: float = 1.0
    misalignment_dy_threshold_mm: float = 1.0
    misalignment_drz_threshold_deg: float = 1.0
    misalignment_dw_threshold_mm: float = 0.5
    misalignment_dh_threshold_mm: float = 0.5
    detection_interval_s: float = 0.1
    reference_tcp_x_mm: float | None = None
    reference_tcp_y_mm: float | None = None
    reference_orientation_deg: float | None = None
    reference_marker_width_mm: float | None = None
    reference_marker_height_mm: float | None = None
    reference_marker_corners_normalized: tuple[tuple[float, float], ...] | None = None
    reference_point_of_interest_normalized: tuple[float, float] | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ShaftAlignmentSettings":
        values = {key: value for key, value in data.items() if key in cls.__dataclass_fields__}
        for key in ("calibration_pose", "capture_pose"):
            if key in values:
                values[key] = (
                    None
                    if values[key] is None
                    else tuple(float(value) for value in values[key])
                )
        if values.get("reference_marker_corners_normalized") is not None:
            values["reference_marker_corners_normalized"] = tuple(
                tuple(float(coordinate) for coordinate in point)
                for point in values["reference_marker_corners_normalized"]
            )
        if values.get("reference_point_of_interest_normalized") is not None:
            values["reference_point_of_interest_normalized"] = tuple(
                float(coordinate)
                for coordinate in values["reference_point_of_interest_normalized"]
            )
        settings = cls(**values)
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.marker_size_mm <= 0.0 or self.minimum_area_px2 < 0.0:
            raise ValueError("Marker size must be positive and minimum area non-negative")
        if len(self.calibration_pose) != 6 or len(self.capture_pose) != 6:
            raise ValueError("Calibration and capture poses must contain six values")
        if self.orientation_strategy not in {"compare", "solve_pnp", "corner_edge"}:
            raise ValueError("Unsupported orientation strategy")
        if self.orientation_primary_strategy not in {"solve_pnp", "corner_edge"}:
            raise ValueError("Unsupported primary orientation strategy")
        if min(self.base_region_width_px, self.base_region_height_px) <= 0:
            raise ValueError("Base region dimensions must be positive")
        if min(
            self.tracking_region_minimum_width_px,
            self.tracking_region_minimum_height_px,
            self.marker_misses_before_region_fallback,
            self.detections_before_tracking,
            self.acquisition_misses_before_reset,
            self.stability_required_samples,
            self.stability_misses_before_reset,
            self.reference_capture_samples,
            self.alignment_check_samples,
        ) <= 0:
            raise ValueError("Sample, tracking, stability, and miss counts must be positive")
        if min(self.tracking_region_padding_px, self.tracking_recovery_expansion_px) < 0:
            raise ValueError("Tracking padding and expansion must be non-negative")
        if not 0.0 < self.tracking_position_filter_alpha <= 1.0:
            raise ValueError("Position filter alpha must be in (0, 1]")
        if not 0.0 <= self.tracking_prediction_gain <= 1.0:
            raise ValueError("Prediction gain must be in [0, 1]")
        if self.tracking_maximum_center_jump_px <= 0.0 or self.tracking_maximum_area_ratio_change <= 1.0:
            raise ValueError("Tracking plausibility limits are invalid")
        thresholds = (
            self.misalignment_dx_threshold_mm, self.misalignment_dy_threshold_mm,
            self.misalignment_drz_threshold_deg, self.misalignment_dw_threshold_mm,
            self.misalignment_dh_threshold_mm,
        )
        if min(thresholds) < 0.1 or max(thresholds) > 5.0:
            raise ValueError("Misalignment thresholds must be in [0.1, 5.0]")
        if self.detection_interval_s < 0.0:
            raise ValueError("Detection interval must be non-negative")
        reference_values = (
            self.reference_tcp_x_mm, self.reference_tcp_y_mm,
            self.reference_orientation_deg, self.reference_marker_width_mm,
            self.reference_marker_height_mm,
        )
        if any(value is not None for value in reference_values) and not all(
            value is not None for value in reference_values
        ):
            raise ValueError("Persisted reference values must be either complete or empty")
        if self.reference_marker_corners_normalized is not None:
            corners = self.reference_marker_corners_normalized
            if len(corners) != 4 or any(len(point) != 2 for point in corners):
                raise ValueError("Reference marker guide must contain four points")
            if any(
                not 0.0 <= coordinate <= 1.0
                for point in corners
                for coordinate in point
            ):
                raise ValueError("Reference marker guide coordinates must be normalized")
        if self.reference_point_of_interest_normalized is not None:
            point = self.reference_point_of_interest_normalized
            if len(point) != 2 or any(not 0.0 <= coordinate <= 1.0 for coordinate in point):
                raise ValueError("Reference point of interest must be normalized")
