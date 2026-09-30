from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PaintHeadCommandResult:
    """Verified write, or a disabled-device dry-run calculation."""

    value: int  # absolute position, except relative dry runs (signed delta)
    register: int
    wrote: bool
    relative: bool


@dataclass(frozen=True)
class PaintHeadDialConfig:
    minimum: int
    spacing: int
    count: int
    enabled: bool


@dataclass(frozen=True)
class PaintAdjustmentOptions:
    length_mm: float
    paint_axis_offset_mm: float
    perpendicular_axis_offset_mm: float


class IPaintAdjustmentService(ABC):
    """Provide the camera role and verified paint-head commands."""

    @abstractmethod
    def get_camera_role(self) -> str: ...

    @abstractmethod
    def get_preset_count(self) -> int: ...

    @abstractmethod
    def is_paint_head_available(self) -> bool: ...

    @abstractmethod
    def get_dial_config(self) -> PaintHeadDialConfig: ...

    @abstractmethod
    def read_current_position(self) -> int | None:
        """Read hardware when enabled; return None without I/O when disabled."""

    @abstractmethod
    def start_single_paint_cycle(self) -> bool:
        """Start one paint cycle without magazine loading or repetition."""

    @abstractmethod
    def get_paint_cycle_state(self) -> str:
        """Return the shared paint process state for initial UI display."""

    @abstractmethod
    def get_adjustment_options(self) -> PaintAdjustmentOptions: ...

    @abstractmethod
    def start_adjustment_cycle(self, options: PaintAdjustmentOptions) -> bool: ...

    @abstractmethod
    def paint_next_section(self, options: PaintAdjustmentOptions) -> bool: ...

    @abstractmethod
    def finish_adjustment_cycle(self) -> bool: ...

    @abstractmethod
    def get_adjustment_status(self) -> tuple[str, float, float]: ...

    @abstractmethod
    def adjust_paint(self, direction: str, degrees: int) -> PaintHeadCommandResult:
        """Move relative whole degrees, or calculate a dry-run delta."""

    @abstractmethod
    def adjust_paint_by_register_units(self, direction: str, units: int) -> PaintHeadCommandResult:
        """Move by signed register units, or calculate a dry-run delta."""

    @abstractmethod
    def go_to_setting(self, setting: int) -> PaintHeadCommandResult:
        """Write an absolute preset, or calculate its dry-run register value."""

    @abstractmethod
    def go_to_position(self, position: int) -> PaintHeadCommandResult:
        """Write any calibrated register position, or preview it without I/O."""
