from __future__ import annotations

from dataclasses import dataclass
from logging import Logger


@dataclass
class GeometryScaleCache:
    """Mutable cache for calibration geometry scale artifacts."""

    entry: tuple[str, float] | None = None


@dataclass(frozen=True)
class PixelToMmContext:
    """Shared inputs for pixel-to-mm conversion strategies."""

    base_z: float
    rz_offset: float
    rx: float
    ry: float
    target_point_name: str
    calibration_frame_name: str
    mode_name: str
    logger: Logger
    geometry_scale_cache: GeometryScaleCache
