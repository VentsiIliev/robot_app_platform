"""
Mapper protocol for camera settings.

The plugin depends only on this interface — no concrete mapper is imported.
The concrete implementation lives in the adapter layer and is injected via DI.
"""
from typing import Protocol

from src.plugin.camera_settings.camera_settings_data import CameraSettingsData


class ISettingsMapper(Protocol):
    """
    Translates between CameraSettingsData (plugin DTO) and the flat dict
    consumed / produced by the SettingsView.
    """

    def to_flat_dict(self, settings: CameraSettingsData) -> dict: ...
    def from_flat_dict(self, flat: dict, base: CameraSettingsData) -> CameraSettingsData: ...

