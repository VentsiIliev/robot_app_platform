import logging
"""
Laser Detection Storage Management

This module provides storage functionality for laser calibration data,
using the same storage pattern as the VisionSystem.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from core.application.ApplicationStorageResolver import get_application_storage_resolver

_logger = logging.getLogger(__name__)


class LaserCalibrationStorage:
    """
    Manages storage of laser calibration data using the ApplicationStorageResolver.

    This ensures calibration data is stored in the proper application storage
    structure alongside other vision system data.
    """

    def __init__(self, app_name: str = "glue_dispensing_application"):
        """
        Initialize laser calibration storage.

        Args:
            app_name: Name of the application (default: glue_dispensing_application)
        """
        self.app_name = app_name
        self.resolver = get_application_storage_resolver()

        # Ensure calibration directory exists
        self.calibration_dir = Path(
            self.resolver.get_calibration_storage_path(app_name, create_if_missing=True)
        )

    def get_calibration_file_path(self, filename: str = "laser_calibration.json") -> str:
        """
        Get the full path to a calibration file.

        Args:
            filename: Name of the calibration file

        Returns:
            str: Full path to the calibration file
        """
        return str(self.calibration_dir / filename)

    def save_calibration(self, calibration_data: Dict[str, Any], filename: str = "laser_calibration.json") -> bool:
        """
        Save calibration data to JSON file.

        Args:
            calibration_data: Dictionary containing calibration data
            filename: Name of the calibration file

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filepath = self.get_calibration_file_path(filename)

            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)

            with open(filepath, "w") as f:
                json.dump(calibration_data, f, indent=4)

            _logger.info(f"[LaserCalibrationStorage] Saved calibration to: {filepath}")

            return True

        except Exception as e:
            _logger.error(f"[LaserCalibrationStorage] Error saving calibration: {e}")

            import traceback
            traceback.print_exc()
            return False

    def load_calibration(self, filename: str = "laser_calibration.json") -> Optional[Dict[str, Any]]:
        """
        Load calibration data from JSON file.

        Args:
            filename: Name of the calibration file

        Returns:
            Optional[Dict]: Calibration data if successful, None otherwise
        """
        try:
            filepath = self.get_calibration_file_path(filename)

            if not os.path.exists(filepath):
                _logger.info(f"[LaserCalibrationStorage] Calibration file not found: {filepath}")

                return None

            with open(filepath, "r") as f:
                data = json.load(f)

            _logger.info(f"[LaserCalibrationStorage] Loaded calibration from: {filepath}")

            return data

        except Exception as e:
            _logger.error(f"[LaserCalibrationStorage] Error loading calibration: {e}")

            import traceback
            traceback.print_exc()
            return None

    def calibration_exists(self, filename: str = "laser_calibration.json") -> bool:
        """
        Check if a calibration file exists.

        Args:
            filename: Name of the calibration file

        Returns:
            bool: True if file exists, False otherwise
        """
        filepath = self.get_calibration_file_path(filename)
        return os.path.exists(filepath)

    def list_calibrations(self) -> list:
        """
        List all calibration files in the calibration directory.

        Returns:
            list: List of calibration filenames
        """
        try:
            if not self.calibration_dir.exists():
                return []

            json_files = list(self.calibration_dir.glob("*.json"))
            return [f.name for f in json_files]

        except Exception as e:
            _logger.error(f"[LaserCalibrationStorage] Error listing calibrations: {e}")

            return []

    def delete_calibration(self, filename: str = "laser_calibration.json") -> bool:
        """
        Delete a calibration file.

        Args:
            filename: Name of the calibration file to delete

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filepath = self.get_calibration_file_path(filename)

            if not os.path.exists(filepath):
                _logger.info(f"[LaserCalibrationStorage] File not found: {filepath}")

                return False

            os.remove(filepath)
            _logger.info(f"[LaserCalibrationStorage] Deleted calibration: {filepath}")

            return True

        except Exception as e:
            _logger.error(f"[LaserCalibrationStorage] Error deleting calibration: {e}")

            return False

    def get_calibration_directory(self) -> str:
        """
        Get the calibration directory path.

        Returns:
            str: Path to calibration directory
        """
        return str(self.calibration_dir)


# Singleton instance for convenience
_storage_instance: Optional[LaserCalibrationStorage] = None


def get_laser_calibration_storage(app_name: str = "glue_dispensing_application") -> LaserCalibrationStorage:
    """
    Get the singleton LaserCalibrationStorage instance.

    Args:
        app_name: Name of the application

    Returns:
        LaserCalibrationStorage: The storage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = LaserCalibrationStorage(app_name)
    return _storage_instance