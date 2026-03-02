import platform
import time

import cv2

import logging
from src.engine.vision.implementation.plvision.PLVision.Camera import Camera


class CameraInitializer:
    def __init__(self, width, height):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.width = width
        self.height = height

    def initializeCameraWithRetry(self, camera_index, max_retries=10, retry_delay=1.0):
        for attempt in range(max_retries):
            try:
                self._logger.info(f"Attempting camera {camera_index} (attempt {attempt + 1}/{max_retries})")
                if attempt > 0:
                    time.sleep(retry_delay)
                test_camera = Camera(camera_index, self.width, self.height)
                if test_camera.cap.isOpened():
                    ret, frame = test_camera.cap.read()
                    if ret and frame is not None:
                        self._logger.info(f"Camera {camera_index} initialised on attempt {attempt + 1}")
                        return test_camera, camera_index
                    test_camera.cap.release()
                    self._logger.warning(f"Camera {camera_index} opened but cannot capture frames")
                else:
                    self._logger.warning(f"Camera {camera_index} failed to open on attempt {attempt + 1}")
            except Exception as e:
                self._logger.error(f"Error on attempt {attempt + 1}: {e}")

        self._logger.warning(f"Camera {camera_index} failed after {max_retries} attempts — searching alternatives")
        return self._findAndInitializeCamera()

    def _findAndInitializeCamera(self):
        for cam_id in range(10):
            try:
                self._logger.info(f"Testing camera index {cam_id}")
                test_camera = Camera(cam_id, self.width, self.height)
                if test_camera.cap.isOpened():
                    ret, frame = test_camera.cap.read()
                    if ret and frame is not None:
                        self._logger.info(f"Found working camera at index {cam_id}")
                        return test_camera, cam_id
                    test_camera.cap.release()
            except Exception as e:
                self._logger.error(f"Error testing camera {cam_id}: {e}")

        if platform.system().lower() == "linux":
            try:
                for cam_id in self.find_first_available_camera():
                    try:
                        test_camera = Camera(cam_id, self.width, self.height)
                        if test_camera.cap.isOpened():
                            self._logger.info(f"Found camera at index {cam_id} (Linux detection)")
                            return test_camera, cam_id
                    except Exception as e:
                        self._logger.error(f"Error with camera {cam_id}: {e}")
            except Exception as e:
                self._logger.error(f"Linux camera detection failed: {e}")

        self._logger.warning("No working cameras found — using dummy camera")
        return Camera(0, self.width, self.height), 0

    def find_first_available_camera(self, max_devices=10):
        import re
        from modules.shared.utils import linuxUtils

        cams = linuxUtils.list_video_devices_v4l2()
        candidate_indices = []
        for name, paths in cams.items():
            if "integrated" in name.lower():
                continue
            for path in paths:
                match = re.search(r"/dev/video(\d+)", path)
                if match:
                    candidate_indices.append(int(match.group(1)))

        available = []
        for cam_id in candidate_indices:
            cap = cv2.VideoCapture(cam_id)
            if cap.isOpened():
                cap.release()
                available.append(cam_id)
        return available
