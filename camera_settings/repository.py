"""
Legacy repository interfaces - DEPRECATED.

Use ICameraSettingsService instead, which combines both settings persistence
and camera actions in a single service interface.
"""
from typing import Protocol

from src.plugins.camera_settings.camera_settings_data import CameraSettingsData


class ICameraSettingsRepository(Protocol):
    def load(self) -> CameraSettingsData: ...
    def save(self, settings: CameraSettingsData) -> None: ...
