import threading
import time
from collections import deque


class FrameGrabber:
    def __init__(self, camera, maxlen=5):
        """
        Threaded camera grabber.
        camera: Camera object with .capture() method
        maxlen: number of frames to keep in buffer
        """
        self.camera = camera
        self.buffer = deque(maxlen=maxlen)
        self.running = False
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._grab_loop, daemon=True)

    def start(self):
        self.running = True
        self.thread.start()

    def _grab_loop(self):
        while self.running:
            frame = self.camera.capture()
            if frame is not None:
                with self.lock:
                    self.buffer.append(frame)
            else:
                time.sleep(0.001)  # avoid busy loop if capture fails

    def get_latest(self):
        with self.lock:
            if self.buffer:
                return self.buffer[-1]
        return None

    def stop(self):
        self.running = False
        self.thread.join()