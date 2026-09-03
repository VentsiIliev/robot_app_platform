from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.applications.shaft_alignment.settings.shaft_alignment_settings import ShaftAlignmentSettings


@dataclass(frozen=True)
class AlignmentThresholds:
    dx_mm: float = 1.0
    dy_mm: float = 1.0
    drz_deg: float = 1.0
    dw_mm: float = 0.5
    dh_mm: float = 0.5


@dataclass(frozen=True)
class AlignmentSnapshot:
    frame: object | None = None
    running: bool = False
    detected: bool = False
    marker_id: int | None = None
    marker_corners_normalized: tuple[tuple[float, float], ...] = ()
    point_of_interest_normalized: tuple[float, float] | None = None
    reference_marker_corners_normalized: tuple[tuple[float, float], ...] = ()
    detection_region_normalized: tuple[float, float, float, float] | None = None
    configuration_warning: bool = False
    tcp_x_mm: float | None = None
    tcp_y_mm: float | None = None
    orientation_deg: float | None = None
    marker_width_mm: float | None = None
    marker_height_mm: float | None = None
    reference_tcp_x_mm: float | None = None
    reference_tcp_y_mm: float | None = None
    reference_orientation_deg: float | None = None
    reference_marker_width_mm: float | None = None
    reference_marker_height_mm: float | None = None
    dx_mm: float | None = None
    dy_mm: float | None = None
    drz_deg: float | None = None
    dw_mm: float | None = None
    dh_mm: float | None = None
    reference_capturing: bool = False
    reference_samples: int = 0
    reference_samples_required: int = 0
    reference_available: bool = False
    misaligned: bool = False
    exceeded_limits: tuple[str, ...] = ()
    message: str = ""


class IShaftAlignmentService(ABC):
    """Platform boundary for shaft-alignment acquisition and calculations."""

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def get_snapshot(self) -> AlignmentSnapshot: ...

    @abstractmethod
    def capture_reference(self, sample_count: int) -> None: ...

    @abstractmethod
    def set_thresholds(self, thresholds: AlignmentThresholds) -> None: ...

    @abstractmethod
    def get_settings(self) -> ShaftAlignmentSettings: ...

    @abstractmethod
    def save_settings(self, settings: ShaftAlignmentSettings) -> None: ...

    @abstractmethod
    def check_alignment(self) -> bool:
        """Return True only when the latest complete comparison is aligned."""
