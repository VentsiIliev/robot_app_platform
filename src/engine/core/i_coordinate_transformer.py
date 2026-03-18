from abc import ABC, abstractmethod
from typing import Tuple


class ICoordinateTransformer(ABC):
    """Transforms a 2D point from one coordinate space to another
    (canonical use: camera pixels → robot mm via homography)."""

    @abstractmethod
    def transform(self, x: float, y: float) -> Tuple[float, float]:
        """Return (x_out, y_out). Raises RuntimeError if not available."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """True if the transformation matrix is loaded and usable."""
        ...

    @abstractmethod
    def reload(self) -> bool:
        """Re-read the matrix from its source.
        Returns True if the transformer is now available.
        Call this after a calibration run writes a new matrix file."""
        ...

    @abstractmethod
    def transform_to_tcp(self, x: float, y: float) -> Tuple[float, float]:
        """Return (x_out, y_out) shifted by the camera-to-TCP offset.
        Raises RuntimeError if the matrix is not loaded or if no camera-to-TCP offset was
        provided at construction time."""
        ...

    @abstractmethod
    def transform_to_tool(self, x: float, y: float) -> Tuple[float, float]:
        """Return (x_out, y_out) shifted by the camera-to-tool offset.
        Raises RuntimeError if the matrix is not loaded or if no camera-to-tool offset was
        provided at construction time."""
        ...

    @abstractmethod
    def inverse_transform(self, x: float, y: float) -> Tuple[float, float]:
        """Return (x_out, y_out) in the source/image space.
        Raises RuntimeError if the inverse mapping is not available."""
        ...
