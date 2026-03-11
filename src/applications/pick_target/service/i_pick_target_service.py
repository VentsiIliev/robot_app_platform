from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

import numpy as np


class IPickTargetService(ABC):

    @abstractmethod
    def capture(self) -> Tuple[Optional[np.ndarray], List[Tuple[float, float]], List[Tuple[float, float]]]:
        """
        Snapshot the current vision state.
        Returns (frame, pixel_centroids [(px, py)], robot_centroids [(rx, ry)]).
        frame may be None if vision is unavailable.
        """

    @abstractmethod
    def move_to(self, robot_x: float, robot_y: float) -> bool:
        """Move robot to (x, y, z=300, rx=180, ry=0, rz=0). Returns success."""

    @abstractmethod
    def move_to_calibration_position(self) -> bool:
        """Move robot to the named CALIBRATION position. Returns success."""

    @abstractmethod
    def set_use_tcp(self, enabled: bool) -> None:
        """When True, transform() uses TCP offsets; when False, uses raw homography."""
