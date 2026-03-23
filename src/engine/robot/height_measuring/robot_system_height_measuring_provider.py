from __future__ import annotations

from abc import ABC, abstractmethod


class RobotSystemHeightMeasuringProvider(ABC):
    """Robot-system adapter that supplies the laser-control implementation."""

    @abstractmethod
    def build_laser_control(self):
        ...
