"""
Laser Detection Configuration

This module contains all configuration parameters for laser detection,
calibration, and height measuring functionality.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LaserDetectionConfig:
    """Configuration for laser line detection."""

    # Detection parameters
    min_intensity: float = 10.0  # Minimum intensity threshold for laser detection
    gaussian_blur_kernel: tuple = (21, 21)  # Kernel size for Gaussian blur
    gaussian_blur_sigma: float = 0.0  # Sigma for Gaussian blur (0 = auto)

    # Detection axis
    default_axis: str = 'y'  # Default detection axis ('x' or 'y')

    # Frame acquisition
    detection_delay_ms: int = 200  # Delay between laser toggle and image capture (ms)
    image_capture_delay_ms: int = 10  # Delay between consecutive image captures (ms)
    detection_samples: int = 5  # Number of frames to median filter
    max_detection_retries: int = 5  # Maximum retry attempts for detection

    # Subpixel refinement
    use_subpixel_refinement: bool = True  # Enable subpixel peak refinement

    def validate(self):
        """Validate configuration parameters."""
        if self.min_intensity < 0:
            raise ValueError("min_intensity must be non-negative")
        if self.detection_delay_ms < 0:
            raise ValueError("detection_delay_ms must be non-negative")
        if self.detection_samples < 1:
            raise ValueError("detection_samples must be at least 1")
        if self.max_detection_retries < 1:
            raise ValueError("max_detection_retries must be at least 1")
        if self.default_axis not in ('x', 'y'):
            raise ValueError("default_axis must be 'x' or 'y'")


@dataclass
class LaserCalibrationConfig:
    """Configuration for laser calibration process."""

    # Calibration movement parameters
    step_size_mm: float = 1  # Step size for each calibration iteration in mm
    num_iterations: int = 50  # Number of calibration steps

    # Safety parameters
    check_safety_limits: bool = True  # Check robot safety limits during calibration

    # Movement parameters
    calibration_velocity: float = 50.0  # Robot velocity during calibration (mm/s)
    calibration_acceleration: float = 10.0  # Robot acceleration during calibration (mm/s²)
    movement_threshold: float = 0.2  # Position threshold for movement completion (mm)
    movement_timeout: float = 2.0  # Timeout for movement completion (seconds)

    # Frame acquisition during calibration
    delay_between_move_detect_ms: int = 1000  # Delay between movement and detection (ms)
    calibration_detection_retries: int = 3  # Max retries for laser detection during calibration
    calibration_max_attempts: int = 5  # Max attempts per calibration point

    # Polynomial fitting
    max_polynomial_degree: int = 6  # Maximum polynomial degree to test for fitting

    def validate(self):
        """Validate configuration parameters."""
        if self.step_size_mm <= 0:
            raise ValueError("step_size_mm must be positive")
        if self.num_iterations < 2:
            raise ValueError("num_iterations must be at least 2")
        if self.calibration_velocity <= 0:
            raise ValueError("calibration_velocity must be positive")
        if self.calibration_acceleration <= 0:
            raise ValueError("calibration_acceleration must be positive")
        if self.max_polynomial_degree < 1:
            raise ValueError("max_polynomial_degree must be at least 1")


@dataclass
class HeightMeasuringConfig:
    """Configuration for height measuring operations."""

    # Measurement parameters
    measurement_delay_ms: int = 300  # Delay for measurement detection (ms)
    measurement_max_retries: int = 5  # Max retries for measurement

    # Movement parameters
    measurement_velocity: float = 20.0  # Robot velocity during measurement (mm/s)
    measurement_acceleration: float = 10.0  # Robot acceleration during measurement (mm/s²)
    measurement_threshold: float = 0.25  # Position threshold for measurement (mm)
    measurement_timeout: float = 10.0  # Timeout for movement during measurement (seconds)
    delay_between_move_detect_ms: int = 500  # Delay between movement and detection (ms)
    # Calibration file
    calibration_filename: str = "laser_calibration.json"  # Name of calibration file

    def validate(self):
        """Validate configuration parameters."""
        if self.measurement_delay_ms < 0:
            raise ValueError("measurement_delay_ms must be non-negative")
        if self.measurement_max_retries < 1:
            raise ValueError("measurement_max_retries must be at least 1")
        if self.measurement_velocity <= 0:
            raise ValueError("measurement_velocity must be positive")
        if self.measurement_acceleration <= 0:
            raise ValueError("measurement_acceleration must be positive")


@dataclass
class LaserDetectionModuleConfig:
    """Complete configuration for laser detection module."""

    detection: LaserDetectionConfig = field(default_factory=LaserDetectionConfig)
    calibration: LaserCalibrationConfig = field(default_factory=LaserCalibrationConfig)
    measuring: HeightMeasuringConfig = field(default_factory=HeightMeasuringConfig)

    def validate(self):
        """Validate all sub-configurations."""
        self.detection.validate()
        self.calibration.validate()
        self.measuring.validate()

    @classmethod
    def from_dict(cls, config_dict: dict) -> 'LaserDetectionModuleConfig':
        """Create configuration from dictionary."""
        detection_config = LaserDetectionConfig(**config_dict.get('detection', {}))
        calibration_config = LaserCalibrationConfig(**config_dict.get('calibration', {}))
        measuring_config = HeightMeasuringConfig(**config_dict.get('measuring', {}))

        config = cls(
            detection=detection_config,
            calibration=calibration_config,
            measuring=measuring_config
        )
        config.validate()
        return config

    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        from dataclasses import asdict
        return {
            'detection': asdict(self.detection),
            'calibration': asdict(self.calibration),
            'measuring': asdict(self.measuring)
        }


# Default configuration instance
DEFAULT_CONFIG = LaserDetectionModuleConfig()