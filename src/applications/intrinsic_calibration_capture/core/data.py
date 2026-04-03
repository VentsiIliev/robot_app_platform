from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import numpy as np


class BoardType(str, Enum):
    CHESSBOARD = "chessboard"
    CHARUCO = "charuco"


@dataclass
class BoardDetection:
    found: bool
    corners_px: Optional[np.ndarray] = None   # shape: (N, 2)
    center_px: Optional[Tuple[float, float]] = None
    bbox_px: Optional[Tuple[float, float, float, float]] = None  # min_x, min_y, max_x, max_y
    width_px: Optional[float] = None
    height_px: Optional[float] = None


@dataclass
class ImageInfo:
    width: int
    height: int


@dataclass
class FeasibleRegion:
    min_cx: float
    min_cy: float
    max_cx: float
    max_cy: float

    def contains(self, cx: float, cy: float) -> bool:
        return self.min_cx <= cx <= self.max_cx and self.min_cy <= cy <= self.max_cy


@dataclass
class TargetRegion:
    name: str
    center_px: Tuple[float, float]
    tol_px: Tuple[float, float]  # half-width, half-height


@dataclass
class CaptureSample:
    region_name: str
    mode: str  # "neutral", "roll", "pitch", "z"
    pose: list
    image_path: Optional[str] = None


class TiltAxis(str, Enum):
    ROLL = "roll"
    PITCH = "pitch"
    YAW = "yaw"


@dataclass
class LocalJacobian2D:
    """
    Maps robot XY motion to image UV motion:
        [du]   [a b] [dx]
        [dv] = [c d] [dy]

    Optional tilt_sensitivity maps TiltAxis → np.array([du_per_deg, dv_per_deg]),
    i.e. the image-space shift in pixels per degree of rotation around that axis.
    """
    J: np.ndarray  # shape (2, 2)
    tilt_sensitivity: Optional[dict] = None  # TiltAxis -> np.array([du/deg, dv/deg])

    def robot_delta_from_pixel_error(self, du: float, dv: float) -> Tuple[float, float]:
        vec = np.array([du, dv], dtype=float)
        try:
            dxy = np.linalg.solve(self.J, vec)
        except np.linalg.LinAlgError as e:
            raise RuntimeError("Jacobian is singular; cannot invert XY mapping.") from e
        return float(dxy[0]), float(dxy[1])

    def predict_board_shift_px(
        self, axis: TiltAxis, angle_deg: float
    ) -> Optional[Tuple[float, float]]:
        """Return (du, dv) predicted image-space shift when tilting by angle_deg around axis."""
        if self.tilt_sensitivity is None:
            return None
        sensitivity = self.tilt_sensitivity.get(axis)
        if sensitivity is None:
            return None
        return float(sensitivity[0] * angle_deg), float(sensitivity[1] * angle_deg)

