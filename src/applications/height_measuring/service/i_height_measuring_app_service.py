from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings


@dataclass
class LaserDetectionResult:
    ok: bool
    message: str
    pixel_coords: Optional[tuple[float, float]] = None
    height_mm: Optional[float] = None
    debug_image: Optional[np.ndarray] = field(default=None, repr=False)
    mask: Optional[np.ndarray] = field(default=None, repr=False)   # ← add this



class IHeightMeasuringAppService(ABC):

    @abstractmethod
    def run_calibration(self) -> tuple[bool, str]: ...

    @abstractmethod
    def is_calibrated(self) -> bool: ...

    @abstractmethod
    def get_calibration_info(self) -> Optional[dict]: ...

    @abstractmethod
    def get_settings(self) -> HeightMeasuringModuleSettings: ...

    @abstractmethod
    def save_settings(self, settings: HeightMeasuringModuleSettings) -> tuple[bool, str]: ...

    @abstractmethod
    def get_latest_frame(self) -> Optional[np.ndarray]: ...

    @abstractmethod
    def reload_calibration(self) -> None: ...

    @abstractmethod
    def laser_on(self) -> tuple[bool, str]: ...

    @abstractmethod
    def laser_off(self) -> tuple[bool, str]: ...

    @abstractmethod
    def detect_once(self) -> LaserDetectionResult: ...

    @abstractmethod
    def cleanup(self) -> None: ...

    @abstractmethod
    def cancel_calibration(self) -> None: ...

