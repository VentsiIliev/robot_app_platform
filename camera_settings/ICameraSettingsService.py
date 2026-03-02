"""
Split service interfaces for the camera settings plugin.

- ISettingsPersistenceService  → load / save CameraSettingsData
- ICameraActionsService        → camera actions (raw mode, capture, calibration)

The merged ICameraSettingsService is kept as a convenience alias for
backward compatibility but new code should depend on the split interfaces.
"""
from typing import Protocol

from src.plugin.camera_settings.camera_settings_data import CameraSettingsData


class ISettingsPersistenceService(Protocol):
    """Responsible only for loading and saving camera settings."""

    def load_settings(self) -> CameraSettingsData: ...
    def save_settings(self, settings: CameraSettingsData) -> None: ...


class ICameraActionsService(Protocol):
    """Responsible only for live camera actions."""

    def set_raw_mode(self, enabled: bool) -> None: ...
    def capture_image(self) -> None: ...
    def calibrate_camera(self) -> None: ...
    def calibrate_robot(self) -> None: ...


# ---------------------------------------------------------------------------
# Backward-compatible alias — satisfies both protocols in one object.
# Prefer injecting the two split interfaces separately.
# ---------------------------------------------------------------------------
class ICameraSettingsService(ISettingsPersistenceService, ICameraActionsService, Protocol):
    """
    Combined protocol (legacy).  New code should depend on
    ISettingsPersistenceService and ICameraActionsService separately.
    """
    ...

