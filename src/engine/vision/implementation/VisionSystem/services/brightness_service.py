import logging
import numpy as np
from typing import Callable, Optional

from src.engine.vision.implementation.plvision.PLVision.PID.BrightnessController import BrightnessController
from src.engine.vision.implementation.VisionSystem.core.settings.CameraSettings import CameraSettings

_logger = logging.getLogger(__name__)

_FALLBACK_AREA = [(940, 612), (1004, 614), (1004, 662), (940, 660)]


class BrightnessService:

    def __init__(
        self,
        camera_settings: CameraSettings,
        area_points_provider: Optional[Callable[[], np.ndarray | None]] = None,
    ):
        self._settings = camera_settings
        self._area_points_provider = area_points_provider
        self._locked_area_points: np.ndarray | None = None
        self._adjustment_locked = False
        self._adjustment = 0.0
        self.brightness_controller = BrightnessController(
            Kp       = camera_settings.get_brightness_kp(),
            Ki       = camera_settings.get_brightness_ki(),
            Kd       = camera_settings.get_brightness_kd(),
            setPoint = camera_settings.get_target_brightness(),
        )

    # ── Broker callback ───────────────────────────────────────────────

    def on_brightness_toggle(self, mode: str) -> None:
        if mode == "start":
            self._settings.set_brightness_auto(True)
        elif mode == "stop":
            self._settings.set_brightness_auto(False)
        else:
            _logger.warning("on_brightness_toggle: unknown mode %r", mode)

    # ── Main operation ────────────────────────────────────────────────

    def adjust(self, image: np.ndarray) -> np.ndarray:
        area = self._get_area_points()

        adjusted = self.brightness_controller.adjustBrightness(image, self._adjustment)
        if self._adjustment_locked:
            return adjusted

        current  = self.brightness_controller.calculateBrightness(adjusted, area)
        error    = self.brightness_controller.target - current

        if abs(error) > 10:
            correction = error * 0.6
        elif abs(error) > 2:
            correction = error * 0.4
        else:
            correction = error

        self._adjustment = float(np.clip(self._adjustment + correction, -255, 255))

        return self.brightness_controller.adjustBrightness(image, self._adjustment)

    def lock_current_area(self) -> bool:
        area = self._read_area_points()
        if area is None:
            return False
        self._locked_area_points = np.array(area, dtype=np.float32)
        return True

    def unlock_area(self) -> None:
        self._locked_area_points = None

    def lock_adjustment(self) -> None:
        self._adjustment_locked = True

    def unlock_adjustment(self) -> None:
        self._adjustment_locked = False

    # ── Private ───────────────────────────────────────────────────────

    def _get_area_points(self) -> np.ndarray:
        if self._locked_area_points is not None:
            return self._locked_area_points
        area = self._read_area_points()
        if area is not None:
            return area
        return np.array(_FALLBACK_AREA, dtype=np.float32)

    def _read_area_points(self) -> np.ndarray | None:
        if self._area_points_provider is not None:
            try:
                points = self._area_points_provider()
                if points is not None and len(points) == 4:
                    return np.array(points, dtype=np.float32)
            except Exception as exc:
                _logger.error("Error reading dynamic brightness area, using settings fallback: %s", exc)
        try:
            pts = self._settings.get_brightness_area_points()
            if pts and len(pts) == 4:
                return np.array([tuple(p) for p in pts], dtype=np.float32)
        except Exception as exc:
            _logger.error("Error reading brightness area from settings, using fallback: %s", exc)
        return None
