from __future__ import annotations

from abc import ABC, abstractmethod


class RobotSystemCalibrationProvider(ABC):
    """Robot-system adapter that supplies the system-specific calibration move."""

    @abstractmethod
    def build_calibration_navigation(self):
        ...
