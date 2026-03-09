from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List

from src.engine.repositories.interfaces.settings_serializer import ISettingsSerializer



@dataclass
class LaserDetectionSettings:
    min_intensity: float = 10.0
    gaussian_blur_kernel: tuple = (21, 21)
    gaussian_blur_sigma: float = 0.0
    default_axis: str = "y"
    detection_delay_ms: int = 200
    image_capture_delay_ms: int = 10
    detection_samples: int = 5
    max_detection_retries: int = 5


@dataclass
class LaserCalibrationSettings:
    step_size_mm: float = 1.0
    num_iterations: int = 50
    calibration_velocity: float = 50.0
    calibration_acceleration: float = 10.0
    movement_threshold: float = 0.2
    movement_timeout: float = 2.0
    delay_between_move_detect_ms: int = 1000
    calibration_max_attempts: int = 5
    max_polynomial_degree: int = 6
    calibration_initial_position: List[float] = field(
        default_factory=lambda: [0.0, 0.0, 0.0, 180.0, 0.0, 0.0]
    )


@dataclass
class HeightMeasuringSettings:
    measurement_velocity: float = 20.0
    measurement_acceleration: float = 10.0
    measurement_threshold: float = 0.25
    measurement_timeout: float = 10.0
    delay_between_move_detect_ms: int = 500


@dataclass
class HeightMeasuringModuleSettings:
    detection: LaserDetectionSettings = field(default_factory=LaserDetectionSettings)
    calibration: LaserCalibrationSettings = field(default_factory=LaserCalibrationSettings)
    measuring: HeightMeasuringSettings = field(default_factory=HeightMeasuringSettings)


class HeightMeasuringSettingsSerializer(ISettingsSerializer[HeightMeasuringModuleSettings]):

    @property
    def settings_type(self) -> str:
        return "height_measuring_settings"

    def get_default(self) -> HeightMeasuringModuleSettings:
        return HeightMeasuringModuleSettings()

    def to_dict(self, s: HeightMeasuringModuleSettings) -> Dict[str, Any]:
        d = asdict(s)
        # tuple → list already done by asdict; keep as-is for JSON
        return d

    def from_dict(self, data: Dict[str, Any]) -> HeightMeasuringModuleSettings:
        det_raw = data.get("detection",  {})
        cal_raw = data.get("calibration", {})
        meas_raw = data.get("measuring", {})

        # gaussian_blur_kernel is serialised as list → restore as tuple
        if "gaussian_blur_kernel" in det_raw and isinstance(det_raw["gaussian_blur_kernel"], list):
            det_raw = {**det_raw, "gaussian_blur_kernel": tuple(det_raw["gaussian_blur_kernel"])}

        return HeightMeasuringModuleSettings(
            detection=LaserDetectionSettings(**det_raw),
            calibration=LaserCalibrationSettings(**cal_raw),
            measuring=HeightMeasuringSettings(**meas_raw),
        )

