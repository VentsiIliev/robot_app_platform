from dataclasses import dataclass


@dataclass(frozen=True)
class StandaloneShaftDetectionConfig:
    """Editable settings for the standalone development runner."""

    marker_id: int = 2
    minimum_area_px2: float = 0.0
    active_work_area: str | None = "paint"
    raw_mode: bool = False
    headless: bool = False
    debug_draw_detected_markers: bool = True
    debug_draw_detection_region: bool = True
    debug_draw_robot_coordinates: bool = True
    draw_initial_detection_region: bool = True

    orientation_strategy: str = "compare"  # "compare", "solve_pnp" or "corner_edge"
    orientation_primary_strategy: str = "solve_pnp"
    marker_size_mm: float = 11.0

    # Pose at which the homography was calibrated and the pose used to capture
    # this test image. Values are robot TCP [X, Y, Z, RX, RY, RZ].
    calibration_pose: tuple[float, float, float, float, float, float] = (
        -29.075, 217.269, 200.076, -179.99, 0.0, 0.0,
    )
    capture_pose: tuple[float, float, float, float, float, float] = (
        257.75, 215.7, 400.1, -179.2, 0.0, 0.0,
    )
    reference_capture_samples: int = 30
    misalignment_dx_threshold_mm: float = 1.0
    misalignment_dy_threshold_mm: float = 1.0
    misalignment_drz_threshold_deg: float = 1.0
    misalignment_dw_threshold_mm: float = 0.5
    misalignment_dh_threshold_mm: float = 0.5

    # Temporary base ROI until it is supplied by the paint_shaft work area.
    base_region_width_px: int = 100
    base_region_height_px: int = 700

    # Adaptive tracking ROI behavior.
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

    # Stable measurement used for robot-space reporting and later verification.
    stability_required_samples: int = 5
    stability_maximum_center_spread_px: float = 5.0
    stability_maximum_orientation_spread_deg: float = 3.0
    stability_misses_before_reset: int = 3

    detection_interval_s: float = 0.1
    run_duration_s: float = 0.0
    verbose_logging: bool = False
    window_title: str = "Paint Shaft Marker Detection"

    def __post_init__(self) -> None:
        if len(self.calibration_pose) != 6 or len(self.capture_pose) != 6:
            raise ValueError("Calibration and capture poses must contain six values")
        if self.reference_capture_samples <= 0:
            raise ValueError("Reference capture sample count must be positive")
        if min(
            self.misalignment_dx_threshold_mm,
            self.misalignment_dy_threshold_mm,
            self.misalignment_drz_threshold_deg,
            self.misalignment_dw_threshold_mm,
            self.misalignment_dh_threshold_mm,
        ) < 0.0:
            raise ValueError("Misalignment thresholds must be non-negative")
        if self.orientation_strategy.strip().lower() not in {"compare", "solve_pnp", "corner_edge"}:
            raise ValueError("Unsupported orientation strategy")
        if self.orientation_primary_strategy.strip().lower() not in {"solve_pnp", "corner_edge"}:
            raise ValueError("Unsupported primary orientation strategy")
        if self.marker_size_mm <= 0.0:
            raise ValueError("Marker size must be positive")
        if self.base_region_width_px <= 0 or self.base_region_height_px <= 0:
            raise ValueError("Base detection region dimensions must be positive")
        if self.tracking_region_padding_px < 0:
            raise ValueError("Tracking region padding must be non-negative")
        if self.tracking_recovery_expansion_px < 0:
            raise ValueError("Tracking recovery expansion must be non-negative")
        if min(
            self.tracking_region_minimum_width_px,
            self.tracking_region_minimum_height_px,
        ) <= 0:
            raise ValueError("Minimum tracking region dimensions must be positive")
        if self.marker_misses_before_region_fallback <= 0:
            raise ValueError("Marker misses before fallback must be positive")
        if self.detections_before_tracking <= 0:
            raise ValueError("Detections before tracking must be positive")
        if self.acquisition_misses_before_reset <= 0:
            raise ValueError("Acquisition misses before reset must be positive")
        if not 0.0 < self.tracking_position_filter_alpha <= 1.0:
            raise ValueError("Tracking position filter alpha must be in (0, 1]")
        if not 0.0 <= self.tracking_prediction_gain <= 1.0:
            raise ValueError("Tracking prediction gain must be in [0, 1]")
        if self.tracking_maximum_center_jump_px <= 0.0:
            raise ValueError("Maximum tracking center jump must be positive")
        if self.tracking_maximum_area_ratio_change <= 1.0:
            raise ValueError("Maximum tracking area ratio change must be greater than 1")
        if self.stability_required_samples <= 0:
            raise ValueError("Required stability samples must be positive")
        if self.stability_misses_before_reset <= 0:
            raise ValueError("Stability misses before reset must be positive")
        if min(
            self.stability_maximum_center_spread_px,
            self.stability_maximum_orientation_spread_deg,
        ) < 0.0:
            raise ValueError("Stability spread limits must be non-negative")
        if self.detection_interval_s < 0.0:
            raise ValueError("Detection interval must be non-negative")
        if self.run_duration_s < 0.0:
            raise ValueError("Run duration must be non-negative")


CONFIG = StandaloneShaftDetectionConfig()
