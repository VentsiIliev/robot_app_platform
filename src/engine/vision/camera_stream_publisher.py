from __future__ import annotations

import logging
import threading
import time

import cv2

from src.engine.core.i_messaging_service import IMessagingService
from src.engine.vision.frame_orientation import apply_orientation, normalize_rotation
from src.shared_contracts.events.vision_events import CameraTopics


class CameraStreamPublisher:
    """Own one V4L2 camera and publish its frames on a role-specific topic."""

    _RECONNECT_DELAY_S = 1.0
    _MAX_READ_FAILURES = 3

    def __init__(
        self,
        role: str,
        device: str | int,
        messaging: IMessagingService,
        width: int = 640,
        height: int = 480,
        fps: int = 15,
        flip_horizontal: bool = False,
        flip_vertical: bool = False,
        rotate_degrees: int = 0,
    ) -> None:
        self._role = role
        self._device = device
        self._messaging = messaging
        self._width = min(max(1, int(width)), 640)
        self._height = min(max(1, int(height)), 480)
        self._fps = max(1, int(fps))
        self._stop_event = threading.Event()
        self._orientation_lock = threading.Lock()
        self._flip_horizontal = bool(flip_horizontal)
        self._flip_vertical = bool(flip_vertical)
        self._rotate_degrees = normalize_rotation(rotate_degrees)
        self._thread: threading.Thread | None = None
        self._capture: cv2.VideoCapture | None = None
        self._logger = logging.getLogger(f"CameraStreamPublisher.{role}")

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"CameraStream-{self._role}",
            daemon=True,
        )
        self._thread.start()

    def set_orientation(self, horizontal: bool, vertical: bool, rotate_degrees: int = 0) -> None:
        """Apply a new capture orientation to every frame published from now on."""
        rotation = normalize_rotation(rotate_degrees)
        with self._orientation_lock:
            self._flip_horizontal = bool(horizontal)
            self._flip_vertical = bool(vertical)
            self._rotate_degrees = rotation

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
            if thread.is_alive():
                self._logger.warning("Camera read is still blocked; stream will close when it returns")
                return
        self._thread = None

    def _run(self) -> None:
        topic = CameraTopics.frame(self._role)
        frame_period = 1.0 / self._fps
        connection_lost = False

        while not self._stop_event.is_set():
            capture = None
            try:
                capture = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
                self._capture = capture
                if not capture.isOpened():
                    if not connection_lost:
                        self._logger.warning("Camera %s is unavailable; retrying", self._device)
                    connection_lost = True
                else:
                    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                    capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
                    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
                    capture.set(cv2.CAP_PROP_FPS, self._fps)
                    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    if connection_lost:
                        self._logger.info("Camera %s reconnected", self._device)
                    connection_lost = False
                    failures = 0

                    while not self._stop_event.is_set():
                        started = time.monotonic()
                        ok, frame = capture.read()
                        if not ok or frame is None:
                            failures += 1
                            if failures >= self._MAX_READ_FAILURES:
                                self._logger.warning(
                                    "Camera %s stopped delivering frames; reconnecting",
                                    self._device,
                                )
                                connection_lost = True
                                break
                            self._stop_event.wait(0.1)
                            continue

                        failures = 0
                        with self._orientation_lock:
                            horizontal = self._flip_horizontal
                            vertical = self._flip_vertical
                            rotate_degrees = self._rotate_degrees
                        frame = apply_orientation(frame, horizontal, vertical, rotate_degrees)
                        self._messaging.publish(
                            topic,
                            {"image": frame, "camera": self._role},
                        )
                        remaining = frame_period - (time.monotonic() - started)
                        if remaining > 0:
                            self._stop_event.wait(remaining)
            except (cv2.error, OSError) as error:
                self._logger.warning("Camera %s failed: %s; reconnecting", self._device, error)
                connection_lost = True
            finally:
                if capture is not None:
                    try:
                        capture.release()
                    except (cv2.error, OSError) as error:
                        self._logger.warning("Could not release camera %s: %s", self._device, error)
                self._capture = None
            self._stop_event.wait(self._RECONNECT_DELAY_S)
