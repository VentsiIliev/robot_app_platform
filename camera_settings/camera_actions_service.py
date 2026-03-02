"""
Legacy camera actions service - DEPRECATED.

Use ICameraSettingsService instead, which combines both settings persistence
and camera actions in a single service interface.
"""
from typing import Protocol


class ICameraActionsService(Protocol):
    """
    DEPRECATED: Use ICameraSettingsService instead.

    Camera action operations (raw mode, capture, calibration).
    """
    def set_raw_mode(self, enabled: bool) -> None: ...
    def capture_image(self) -> None: ...
    def calibrate_camera(self) -> None: ...
    def calibrate_robot(self) -> None: ...
