from typing import Optional

import cv2
import numpy as np

from src.applications.height_measuring.service.i_height_measuring_app_service import (
    IHeightMeasuringAppService,
    LaserDetectionResult,
)
from src.engine.robot.height_measuring.settings import HeightMeasuringModuleSettings


class StubHeightMeasuringAppService(IHeightMeasuringAppService):

    def run_calibration(self) -> tuple[bool, str]:
        print("[Stub] run_calibration")
        return True, "Stub calibration complete"

    def is_calibrated(self) -> bool:
        return True

    def get_calibration_info(self) -> Optional[dict]:
        return {"degree": 3, "mse": 0.0042, "points": 50}

    def get_settings(self) -> HeightMeasuringModuleSettings:
        return HeightMeasuringModuleSettings()

    def save_settings(self, settings: HeightMeasuringModuleSettings) -> tuple[bool, str]:
        print(f"[Stub] save_settings: {settings}")
        return True, "Settings saved"

    def get_latest_frame(self) -> Optional[np.ndarray]:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[240, :, 1] = 200
        return frame

    def reload_calibration(self) -> None:
        print("[Stub] reload_calibration")

    def laser_on(self) -> tuple[bool, str]:
        print("[Stub] laser_on")
        return True, "Laser on"

    def laser_off(self) -> tuple[bool, str]:
        print("[Stub] laser_off")
        return True, "Laser off"

    def detect_once(self) -> LaserDetectionResult:
        print("[Stub] detect_once")
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        image[240:244, :, 1] = 180
        cv2.circle(image, (320, 242), 8, (0, 0, 255), 2)
        cv2.drawMarker(image, (320, 242), (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
        return LaserDetectionResult(
            ok=True,
            message="Detected at (320.0, 242.0)",
            pixel_coords=(320.0, 242.0),
            height_mm=12.47,
            debug_image=image,
        )

    def cleanup(self) -> None:
        print("[Stub] cleanup")

    def cancel_calibration(self) -> None:
        print("[Stub] cancel_calibration")


