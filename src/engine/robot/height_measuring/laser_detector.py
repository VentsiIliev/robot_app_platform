import logging
from typing import Optional, Tuple

import cv2
import numpy as np

from src.engine.robot.height_measuring.settings import LaserDetectionSettings

_logger = logging.getLogger(__name__)


class LaserDetector:
    def __init__(self, config: LaserDetectionSettings):
        self._config = config
        self.last_closest_point: Optional[Tuple[float, float]] = None
        self.last_bright_point = None

    def _subpixel_quadratic(self, idx: int, arr: np.ndarray) -> float:
        n = len(arr)
        if 1 <= idx < n - 1:
            L = float(arr[idx - 1])
            C = float(arr[idx])
            R = float(arr[idx + 1])
            denom = L - 2 * C + R
            if denom != 0:
                return idx + 0.5 * (L - R) / denom
        return float(idx)

    def detect_laser_line(
        self,
        on_frame: np.ndarray,
        off_frame: np.ndarray,
        axis: Optional[str] = None,
    ) -> Tuple[Optional[np.ndarray], Optional[tuple], Optional[Tuple[float, float]]]:
        if on_frame is None or off_frame is None:
            _logger.warning("detect_laser_line: on_frame or off_frame is None")
            return None, None, None

        axis = axis or self._config.default_axis
        diff = np.clip(
            on_frame[:, :, 2].astype(np.float32) - off_frame[:, :, 2].astype(np.float32),
            0, None,
        )
        diff = cv2.GaussianBlur(
            diff,
            self._config.gaussian_blur_kernel,
            self._config.gaussian_blur_sigma,
        )
        h, w = diff.shape
        min_i = self._config.min_intensity

        if axis == "y":
            points = []
            for i in range(h):
                row = diff[i, :]
                if np.max(row) > min_i:
                    idx_max = int(np.argmax(row))
                    points.append((self._subpixel_quadratic(idx_max, row), float(i)))
        else:
            points = []
            for j in range(w):
                col = diff[:, j]
                if np.max(col) > min_i:
                    idx_max = int(np.argmax(col))
                    points.append((float(j), self._subpixel_quadratic(idx_max, col)))

        closest_point = None
        if points:
            cx, cy = w / 2.0, h / 2.0
            closest_point = min(points, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)

        bright = cv2.minMaxLoc(diff)[3]
        mask = np.zeros((h, w), np.uint8)
        for (x, y) in points:
            mask[int(round(y)), int(round(x))] = 255

        self.last_bright_point = bright
        self.last_closest_point = closest_point
        _logger.debug("Detected %d laser points, closest=%s", len(points), closest_point)
        return mask, bright, closest_point

