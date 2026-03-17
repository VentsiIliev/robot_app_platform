import logging
import numpy as np
from typing import Tuple

from src.engine.core.i_coordinate_transformer import ICoordinateTransformer

_MISSING = object()  # sentinel — distinguishes "not provided" from None


class HomographyTransformer(ICoordinateTransformer):
    def __init__(self, matrix_path: str,
                 tcp_x_offset: float = _MISSING,
                 tcp_y_offset: float = _MISSING):
        self._matrix_path = matrix_path
        self._H: np.ndarray | None = None
        self._H_inv: np.ndarray | None = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self._tcp_x: float | None = None if tcp_x_offset is _MISSING else float(tcp_x_offset)
        self._tcp_y: float | None = None if tcp_y_offset is _MISSING else float(tcp_y_offset)
        self._has_tcp = (tcp_x_offset is not _MISSING) and (tcp_y_offset is not _MISSING)
        self._load()

    def _load(self) -> None:
        try:
            self._H = np.load(self._matrix_path)
            self._H_inv = np.linalg.inv(self._H)
            self._logger.info("Homography matrix loaded from %s", self._matrix_path)
        except Exception as exc:
            self._logger.warning("Homography matrix not available at %s: %s",
                                 self._matrix_path, exc)
            self._H = None
            self._H_inv = None

    def is_available(self) -> bool:
        return self._H is not None

    def reload(self) -> bool:
        self._load()
        return self.is_available()

    def transform(self, x: float, y: float) -> Tuple[float, float]:
        if self._H is None:
            raise RuntimeError("Homography matrix not loaded")
        pt = np.array([x, y, 1.0])
        robot_pt = self._H @ pt
        robot_pt /= robot_pt[2]
        return float(robot_pt[0]), float(robot_pt[1])

    def transform_to_tcp(self, x: float, y: float) -> Tuple[float, float]:
        if not self._has_tcp:
            raise RuntimeError(
                "TCP offsets were not provided at construction — "
                "pass tcp_x_offset and tcp_y_offset to HomographyTransformer"
            )
        cx, cy = self.transform(x, y)
        return cx + self._tcp_x, cy + self._tcp_y

    def inverse_transform(self, x: float, y: float) -> Tuple[float, float]:
        if self._H_inv is None:
            raise RuntimeError("Homography inverse matrix not loaded")
        pt = np.array([x, y, 1.0])
        image_pt = self._H_inv @ pt
        image_pt /= image_pt[2]
        return float(image_pt[0]), float(image_pt[1])
