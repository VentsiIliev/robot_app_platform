from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, List, Tuple
from src.applications.camera_settings.camera_settings_data import CameraSettingsData


@dataclass(frozen=True)
class CameraDeviceOption:
    device: str
    capture_node: str
    connected: bool


@dataclass(frozen=True)
class CameraOrientation:
    """Capture orientation for one camera role.

    Rotation is always applied first, then the mirror, so ``flip_vertical``
    keeps meaning "mirror the image as displayed" for any rotation.
    """

    VALID_ROTATIONS: ClassVar[tuple[int, ...]] = (0, 90, 180, 270)

    flip_horizontal: bool = False
    flip_vertical: bool = False
    rotate_degrees: int = 0

    @property
    def transposes_frame(self) -> bool:
        return self.rotate_degrees in (90, 270)


@dataclass(frozen=True)
class CameraDevicesState:
    assignments: dict[str, str]
    options: tuple[CameraDeviceOption, ...]
    orientation: dict[str, CameraOrientation] = field(default_factory=dict)


class ICameraSettingsService(ABC):

    @abstractmethod
    def load_settings(self) -> CameraSettingsData: ...

    @abstractmethod
    def save_settings(self, settings: CameraSettingsData) -> None: ...

    @abstractmethod
    def set_raw_mode(self, enabled: bool) -> None: ...

    @abstractmethod
    def update_settings(self, settings: dict) -> tuple[bool, str]: ...

    @abstractmethod
    def save_work_area(self, area_type: str, points: List[Tuple[float, float]]) -> tuple[bool, str]: ...

    @abstractmethod
    def get_work_area(self, area_type: str) -> tuple[bool, str, List[Tuple[float, float]]]: ...

    @abstractmethod
    def load_camera_devices(self) -> CameraDevicesState: ...

    @abstractmethod
    def save_camera_devices(
        self,
        assignments: dict[str, str],
        orientation: dict[str, CameraOrientation],
    ) -> None: ...
