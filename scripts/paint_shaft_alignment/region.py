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


class SelectableDetectionRegionProvider:
    """Uses a drawn ROI when present and otherwise delegates to a default provider."""

    def __init__(self, default_provider: DetectionRegionProvider) -> None:
        self._default_provider = default_provider
        self._selected_region: PixelRegion | None = None

    @property
    def selected_region(self) -> PixelRegion | None:
        return self._selected_region

    def select(self, start: tuple[int, int], end: tuple[int, int]) -> bool:
        left, right = sorted((start[0], end[0]))
        top, bottom = sorted((start[1], end[1]))
        if right == left or bottom == top:
            return False
        self._selected_region = PixelRegion(left, top, right - left, bottom - top)
        return True

    def clear(self) -> None:
        self._selected_region = None

    def resolve(self, image_width: int, image_height: int) -> PixelRegion:
        if self._selected_region is None:
            return self._default_provider.resolve(image_width, image_height)
        region = self._selected_region
        left = min(max(0, region.x), max(0, image_width - 1))
        top = min(max(0, region.y), max(0, image_height - 1))
        right = min(image_width, max(left + 1, region.right))
        bottom = min(image_height, max(top + 1, region.bottom))
        return PixelRegion(left, top, right - left, bottom - top)
