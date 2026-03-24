from abc import ABC, abstractmethod
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
