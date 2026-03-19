import threading
import time
import logging
from collections import deque


_logger = logging.getLogger(__name__)


class FrameGrabber:
    def __init__(
        self,
        camera,
        maxlen=5,
        *,
        read_timeout_s=0.25,
        restart_after_failures=4,
        restart_cooldown_s=1.0,
        post_restart_settle_s=0.2,
        stale_frame_timeout_s=1.0,
    ):
        """
        Threaded camera grabber.
        camera: Camera object with .capture() method
        maxlen: number of frames to keep in buffer
        read_timeout_s: timeout passed to camera.capture() for each frame read
        restart_after_failures: consecutive failed reads before attempting restart
        restart_cooldown_s: minimum time between restart attempts
        post_restart_settle_s: short wait after restarting the stream
        stale_frame_timeout_s: how long the latest buffered frame may be reused
            before it is considered stale and hidden from callers
        """
        self.camera = camera
        self.buffer = deque(maxlen=maxlen)
        self.running = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._grab_loop, daemon=True)
        self.read_timeout_s = float(read_timeout_s)
        self.restart_after_failures = max(1, int(restart_after_failures))
        self.restart_cooldown_s = float(restart_cooldown_s)
        self.post_restart_settle_s = float(post_restart_settle_s)
        self.stale_frame_timeout_s = float(stale_frame_timeout_s)
        self._consecutive_failures = 0
        self._last_restart_at = 0.0
        self._last_frame_at = 0.0

    def start(self):
        self.running = True
        self.thread.start()

    def _grab_loop(self):
        while self.running:
            frame = self.camera.capture(timeout=self.read_timeout_s)
            if frame is not None:
                self._consecutive_failures = 0
                with self.lock:
                    self.buffer.append(frame)
                    self._last_frame_at = time.time()
            else:
                self._consecutive_failures += 1
                if self._should_restart_stream():
                    self._restart_stream()
                time.sleep(0.001)  # avoid busy loop if capture fails

    def _should_restart_stream(self) -> bool:
        if self._consecutive_failures < self.restart_after_failures:
            return False
        if not hasattr(self.camera, "start_stream") or not hasattr(self.camera, "stop_stream"):
            return False
        return (time.time() - self._last_restart_at) >= self.restart_cooldown_s

    def _restart_stream(self) -> None:
        self._last_restart_at = time.time()
        _logger.warning(
            "FrameGrabber restarting camera stream after %d consecutive capture failures",
            self._consecutive_failures,
        )
        with self.lock:
            self.buffer.clear()
            self._last_frame_at = 0.0
        try:
            self.camera.stop_stream()
        except Exception:
            _logger.exception("FrameGrabber failed to stop camera stream during recovery")
        time.sleep(self.post_restart_settle_s)
        try:
            self.camera.start_stream()
        except Exception:
            _logger.exception("FrameGrabber failed to start camera stream during recovery")
        self._consecutive_failures = 0

    def get_latest(self):
        with self.lock:
            if not self.buffer:
                return None
            if self._last_frame_at and (time.time() - self._last_frame_at) > self.stale_frame_timeout_s:
                return None
            return self.buffer[-1]
        return None

    def stop(self):
        self.running = False
        self.thread.join()
