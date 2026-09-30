from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Tuple
from src.applications.camera_settings.camera_settings_data import CameraSettingsData


@dataclass(frozen=True)
class CameraDeviceOption:
    device: str
    capture_node: str
    connected: bool


@dataclass(frozen=True)
class CameraDevicesState:
    assignments: dict[str, str]
    options: tuple[CameraDeviceOption, ...]
    flips: dict[str, tuple[bool, bool]] = field(default_factory=dict)


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
        flips: dict[str, tuple[bool, bool]],
    ) -> None: ...
