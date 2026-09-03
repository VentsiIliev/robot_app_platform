from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Tuple


PixelPoint = Tuple[float, float]


@dataclass(frozen=True)
class PixelRegion:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


class DetectionRegionProvider(Protocol):
    """Resolves the image region searched for the shaft marker."""

    def resolve(self, image_width: int, image_height: int) -> PixelRegion: ...


@dataclass(frozen=True)
class CenteredDetectionRegionProvider:
    """Temporary provider until a paint-shaft work-area ROI is available."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Detection region dimensions must be positive")

    def resolve(self, image_width: int, image_height: int) -> PixelRegion:
        width = min(self.width, image_width)
        height = min(self.height, image_height)
        return PixelRegion(
            x=max(0, (image_width - width) // 2),
            y=max(0, (image_height - height) // 2),
            width=width,
            height=height,
        )

