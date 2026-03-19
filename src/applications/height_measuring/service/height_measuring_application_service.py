import logging
import threading
from typing import Optional, Protocol

import cv2
import numpy as np

from src.applications.height_measuring.service.i_height_measuring_app_service import (
    IHeightMeasuringAppService,
    LaserDetectionResult,
)
from src.engine.repositories.interfaces.settings_repository import ISettingsRepository
from src.engine.robot.height_measuring.i_height_measuring_service import IHeightMeasuringService
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)


class _ILaserCalibrator(Protocol):
    def calibrate(self, initial_position: list) -> bool: ...


class _ILaserOps(Protocol):
    def turn_on(self) -> None: ...
    def turn_off(self) -> None: ...
    def detect(self) -> tuple: ...
    def restore(self) -> None: ...



class HeightMeasuringApplicationService(IHeightMeasuringAppService):

    def __init__(
        self,
        vision_service: Optional[IVisionService],
        height_measuring_service: IHeightMeasuringService,
        calibration_service: _ILaserCalibrator,
        settings_repo: ISettingsRepository,
        laser_ops: Optional[_ILaserOps] = None,
    ):
        self._vision        = vision_service
        self._height_svc    = height_measuring_service
        self._calib_svc     = calibration_service
        self._settings_repo = settings_repo
        self._laser_ops     = laser_ops
        self._stop_event = threading.Event()

    def run_calibration(self) -> tuple[bool, str]:
        self._stop_event.clear()
        try:
            settings = self._settings_repo.load()
            initial_pos = settings.calibration.calibration_initial_position
            ok = self._calib_svc.calibrate(initial_pos, stop_event=self._stop_event)
            if ok:
                self._height_svc.reload_calibration()
                return True, "Calibration complete"
            if self._stop_event.is_set():
                return False, "Calibration cancelled"
            return False, "Calibration failed — check laser and robot position"
        except Exception as e:
            _logger.error("Calibration error: %s", e)
            return False, f"Calibration error: {e}"


    def cancel_calibration(self) -> None:
        self._stop_event.set()

    def is_calibrated(self) -> bool:
        return self._height_svc.is_calibrated()

    def get_calibration_info(self) -> Optional[dict]:
        data = self._height_svc.get_calibration_data()
        if data is None or not data.is_calibrated():
            return None
        return {
            "degree": data.polynomial_degree,
            "mse":    data.polynomial_mse,
            "points": len(data.calibration_points),
        }

    def get_settings(self) -> HeightMeasuringModuleSettings:
        return self._settings_repo.load()

    def save_settings(self, settings: HeightMeasuringModuleSettings) -> tuple[bool, str]:
        try:
            self._settings_repo.save(settings)
            return True, "Settings saved"
        except Exception as e:
            _logger.error("Failed to save settings: %s", e)
            return False, f"Failed to save settings: {e}"

    def get_latest_frame(self) -> Optional[np.ndarray]:
        if self._vision is None:
            return None
        return self._vision.get_latest_frame()

    def reload_calibration(self) -> None:
        self._height_svc.reload_calibration()

    def laser_on(self) -> tuple[bool, str]:
        if self._laser_ops is None:
            return False, "Laser control not available"
        try:
            self._laser_ops.turn_on()
            return True, "Laser on"
        except Exception as e:
            _logger.error("laser_on error: %s", e)
            return False, f"Failed to turn laser on: {e}"

    def laser_off(self) -> tuple[bool, str]:
        if self._laser_ops is None:
            return False, "Laser control not available"
        try:
            self._laser_ops.turn_off()
            return True, "Laser off"
        except Exception as e:
            _logger.error("laser_off error: %s", e)
            return False, f"Failed to turn laser off: {e}"

    def detect_once(self) -> LaserDetectionResult:
        if self._laser_ops is None:
            _logger.warning("Laser operations not available for detection")
            return LaserDetectionResult(ok=False, message="Laser detection not available")
        try:
            mask, bright, closest = self._laser_ops.detect()
            if closest is not None:
                x, y = closest
                _logger.debug("Detected laser at x=%d, y=%d", x, y)
                debug_image = self._build_debug_image(mask, closest)
                height_mm   = self._estimate_height(float(x))
                return LaserDetectionResult(
                    ok=True,
                    message=f"Detected at ({x:.1f}, {y:.1f})",
                    pixel_coords=(float(x), float(y)),
                    height_mm=height_mm,
                    debug_image=debug_image,
                    mask=mask
                )
            _logger.warning("No laser line detected during detect_once")
            return LaserDetectionResult(ok=False, message="No laser line detected")
        except Exception as e:
            _logger.error("detect_once error: %s", e)
            return LaserDetectionResult(ok=False, message=f"Detection error: {e}")

    def _build_debug_image(self, mask: Optional[np.ndarray], closest: Optional[tuple]) -> np.ndarray:
        frame = self.get_latest_frame()
        base  = frame.copy() if frame is not None else np.zeros((480, 640, 3), dtype=np.uint8)
        if mask is not None:
            # The detector writes one pixel per column — dilate to make the line visible
            kernel       = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 9))
            mask_dilated = cv2.dilate(mask, kernel)
            green_channel = np.zeros_like(base)
            green_channel[:, :, 1] = mask_dilated
            base = cv2.addWeighted(base, 1.0, green_channel, 1.0, 0)
        if closest is not None:
            cx, cy = int(closest[0]), int(closest[1])
            cv2.circle(base, (cx, cy), 8, (0, 0, 255), 2)
            cv2.drawMarker(base, (cx, cy), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
        return base

    def _estimate_height(self, pixel_x: float) -> Optional[float]:
        data = self._height_svc.get_calibration_data()
        if data is None or not data.is_calibrated():
            return None
        delta    = data.zero_reference_coords[0] - pixel_x
        features = [delta ** (i + 1) for i in range(data.polynomial_degree)]
        raw_height = sum(c * f for c, f in zip(data.polynomial_coefficients, features)) + data.polynomial_intercept
        return raw_height - float(getattr(data, "zero_height_offset_mm", 0.0))

    def cleanup(self) -> None:
        if self._laser_ops is None:
            return
        try:
            self._laser_ops.restore()
        except Exception:
            _logger.warning("cleanup: laser restore failed", exc_info=True)
