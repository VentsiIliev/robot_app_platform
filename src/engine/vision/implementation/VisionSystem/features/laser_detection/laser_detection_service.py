import logging
import time

import numpy as np

from modules.VisionSystem.laser_detection.laser_detector import LaserDetector
from modules.VisionSystem.laser_detection.config import LaserDetectionConfig
from modules.shared.tools.Laser import Laser

_logger = logging.getLogger(__name__)


class LaserDetectionService:
    def __init__(self, detector: LaserDetector, laser: Laser, vision_service, config: LaserDetectionConfig = None):
        """
        Initialize laser detection service.

        Args:
            detector: LaserDetector instance
            laser: Laser control instance
            vision_service: VisionService instance for frame access
            config: LaserDetectionConfig instance (uses default if None)
        """
        self.detector = detector
        self.laser = laser
        self.vision_service = vision_service
        self.config = config if config is not None else LaserDetectionConfig()
        self.last_on_frame = None
        self.last_off_frame = None
        self.laser_status = 0


    # -------------------------------------------------
    # Toggle laser
    # -------------------------------------------------
    def toggle_laser(self):
        if self.laser_status == 0:
            self.laser.turnOn()
            self.laser_status = 1
        else:
            self.laser.turnOff()
            self.laser_status = 0

    # -------------------------------------------------
    # Frame updates
    # -------------------------------------------------
    def update_frame(self, frame):
        if self.laser_status == 1:
            self.last_on_frame = frame.copy()
        else:
            self.last_off_frame = frame.copy()



    def detect(self):
        """
        Detect laser line using median of multiple ON/OFF frames.

        Args:
            axis: 'x' or 'y' (uses config default if None)
            delay_ms: time between frame grabs (uses config default if None)
            samples: number of frames for median (uses config default if None)
            max_retries: attempts before giving up (uses config default if None)

        Returns:
            tuple: (mask, bright, closest) or (None, None, None) if detection fails
        """
        # Use config defaults if not specified
        axis =self.config.default_axis
        delay_between_laser_toggle_and_capture = self.config.detection_delay_ms
        image_capture_delay_ms = self.config.image_capture_delay_ms
        samples = self.config.detection_samples
        max_retries =  self.config.max_detection_retries

        for attempt in range(max_retries):

            # ---------------------------
            # 1. Collect OFF frames
            # ---------------------------
            self.laser.turnOff()
            time.sleep(delay_between_laser_toggle_and_capture/1000)
            off_frames = []
            for i in range(samples):
                time.sleep(image_capture_delay_ms / 1000.0)
                frame = self.vision_service.latest_frame
                if frame is not None:
                    off_frames.append(frame.copy())

            if len(off_frames) < samples:
                continue

            # Median OFF
            off_med = np.median(np.stack(off_frames, axis=0), axis=0).astype(np.uint8)

            # ---------------------------
            # 2. Collect ON frames
            # ---------------------------
            self.laser.turnOn()
            time.sleep(delay_between_laser_toggle_and_capture / 1000)
            on_frames = []
            for i in range(samples):
                time.sleep(image_capture_delay_ms / 1000.0)
                frame = self.vision_service.latest_frame
                if frame is not None:
                    on_frames.append(frame.copy())

            if len(on_frames) < samples:
                continue

            # Median ON
            on_med = np.median(np.stack(on_frames, axis=0), axis=0).astype(np.uint8)
            self.last_off_frame = off_med.copy()
            self.last_on_frame = on_med.copy()

            # ---------------------------
            # 3. Detect laser from median images
            # ---------------------------
            mask, bright, closest = self.detector.detect_laser_line(on_med, off_med, axis)

            if closest is not None:
                _logger.info(f"[LaserDetection] Success at {closest}")

                return mask, bright, closest

            _logger.info(f"[LaserDetection] Attempt {attempt + 1}: No detection")


        _logger.error("[LaserDetection] FAILED after retries")

        return None, None, None

