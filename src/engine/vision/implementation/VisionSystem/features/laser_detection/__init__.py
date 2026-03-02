"""
Laser Detection Module

This module provides laser detection, calibration, and height measuring functionality.
All configuration is centralized in config classes, and storage uses the ApplicationStorageResolver pattern.
"""

from modules.VisionSystem.laser_detection.config import (
    LaserDetectionConfig,
    LaserCalibrationConfig,
    HeightMeasuringConfig,
    LaserDetectionModuleConfig,
    DEFAULT_CONFIG
)

from modules.VisionSystem.laser_detection.storage import (
    LaserCalibrationStorage,
    get_laser_calibration_storage
)

from modules.VisionSystem.laser_detection.laser_detector import LaserDetector
from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService
from modules.VisionSystem.laser_detection.laser_calibration_service import LaserDetectionCalibration
from modules.VisionSystem.laser_detection.height_measuring import HeightMeasuringService

__all__ = [
    # Configuration
    'LaserDetectionConfig',
    'LaserCalibrationConfig',
    'HeightMeasuringConfig',
    'LaserDetectionModuleConfig',
    'DEFAULT_CONFIG',

    # Storage
    'LaserCalibrationStorage',
    'get_laser_calibration_storage',

    # Services
    'LaserDetector',
    'LaserDetectionService',
    'LaserDetectionCalibration',
    'HeightMeasuringService',
]