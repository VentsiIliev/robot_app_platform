from abc import ABC, abstractmethod
from typing import List, Tuple
from src.applications.camera_settings.camera_settings_data import CameraSettingsData


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
