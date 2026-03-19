import logging
import time
from typing import List, Optional, Tuple

import numpy as np

from src.engine.hardware.laser.i_laser_control import ILaserControl
from src.engine.robot.height_measuring.laser_detector import LaserDetector
from src.engine.robot.height_measuring.settings import LaserDetectionSettings
from src.engine.vision.i_exposure_control import IExposureControl
from src.engine.vision.i_vision_service import IVisionService

_logger = logging.getLogger(__name__)


class LaserDetectionService:
    def __init__(
        self,
        detector: LaserDetector,
        laser: ILaserControl,
        vision_service: IVisionService,
        config: Optional[LaserDetectionSettings] = None,
        exposure_control: Optional[IExposureControl] = None,
    ):
        self._detector  = detector
        self._laser     = laser
        self._vision    = vision_service
        self._config    = config or LaserDetectionSettings()
        self._exposure  = exposure_control
        self._session_depth = 0

    def begin_measurement_session(self) -> None:
        self._session_depth += 1
        if self._session_depth == 1 and self._exposure:
            _logger.debug("Disabling auto-exposure for laser measurement session")
            self._exposure.set_auto_exposure(False)

    def end_measurement_session(self) -> None:
        if self._session_depth <= 0:
            return
        self._session_depth -= 1
        if self._session_depth == 0 and self._exposure:
            _logger.debug("Restoring auto-exposure after laser measurement session")
            self._exposure.set_auto_exposure(True)

    def detect(self) -> Tuple[Optional[np.ndarray], Optional[tuple], Optional[Tuple[float, float]]]:
        if self._exposure and self._session_depth == 0:
            _logger.debug("Disabling auto-exposure for laser detection")
            self._exposure.set_auto_exposure(False)
        try:
            return self._detect()
        finally:
            if self._exposure and self._session_depth == 0:
                _logger.debug("Restoring auto-exposure after laser detection")
                self._exposure.set_auto_exposure(True)

    def _detect(self) -> Tuple[Optional[np.ndarray], Optional[tuple], Optional[Tuple[float, float]]]:
        cfg         = self._config
        toggle_wait = cfg.detection_delay_ms / 1000.0
        frame_wait  = cfg.image_capture_delay_ms / 1000.0

        for attempt in range(cfg.max_detection_retries):
            self._laser.turn_off()
            time.sleep(toggle_wait)
            off_frames = self._collect_frames(cfg.detection_samples, frame_wait)
            if len(off_frames) < cfg.detection_samples:
                _logger.warning("Attempt %d: only %d OFF frames", attempt + 1, len(off_frames))
                continue

            self._laser.turn_on()
            time.sleep(toggle_wait)
            on_frames = self._collect_frames(cfg.detection_samples, frame_wait)
            if len(on_frames) < cfg.detection_samples:
                _logger.warning("Attempt %d: only %d ON frames", attempt + 1, len(on_frames))
                continue

            off_med = np.median(np.stack(off_frames), axis=0).astype(np.uint8)
            on_med  = np.median(np.stack(on_frames),  axis=0).astype(np.uint8)

            mask, bright, closest = self._detector.detect_laser_line(
                on_med, off_med, cfg.default_axis
            )
            if closest is not None:
                _logger.info("Laser detected at %s (attempt %d)", closest, attempt + 1)
                return mask, bright, closest

            _logger.warning("Attempt %d/%d: no laser line detected", attempt + 1, cfg.max_detection_retries)

        _logger.error("Laser detection failed after %d attempts", cfg.max_detection_retries)
        return None, None, None

    def _collect_frames(self, count: int, delay_s: float) -> List[np.ndarray]:
        frames = []
        for _ in range(count):
            time.sleep(delay_s)
            frame = self._vision.get_latest_frame()
            if frame is not None:
                frames.append(frame.copy())
        return frames

    @property
    def laser(self) -> ILaserControl:
        return self._laser

    def restore(self) -> None:
        try:
            self._laser.turn_off()
        except Exception:
            pass
        self._session_depth = 0
        if self._exposure:
            try:
                self._exposure.set_auto_exposure(True)
            except Exception:
                pass

    def turn_on(self) -> None:
        self._laser.turn_on()

    def turn_off(self) -> None:
        self._laser.turn_off()
