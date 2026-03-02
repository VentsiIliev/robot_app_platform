import time

import cv2


class RemoteCamera:
    """
    Wraps an MJPEG HTTP stream as a Camera-like object with a .capture() method.
    Can be used in VisionSystem as a drop-in replacement.
    """

    def __init__(self, url, width=None, height=None, fps=None):
        """
        :param url: MJPEG stream URL (e.g., 'http://127.0.0.1:5000/video_feed')
        :param width: optional desired width
        :param height: optional desired height
        :param fps: optional desired FPS (some streams ignore this)
        """
        self.url = url
        self.width = width
        self.height = height
        self.requested_fps = fps
        self.cap = cv2.VideoCapture(url)
        self.active = self.cap.isOpened()
        if not self.active:
            raise RuntimeError(f"Failed to open remote camera at {url}")

        if self.width and self.height:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            time.sleep(0.05)

    def capture(self, grab_only=False, timeout=1.0):
        """
        Mimics the Camera.capture() method.
        :param grab_only: ignored (for API compatibility)
        :param timeout: seconds to wait for a frame
        :return: frame or None
        """
        if not self.active:
            return None

        start_time = time.time()
        while True:
            ret, frame = self.cap.read()
            if ret:
                return frame
            if (time.time() - start_time) > timeout:
                return None
            time.sleep(0.001)

    def isOpened(self):
        self.active = self.cap.isOpened()
        return self.active

    def close(self):
        if self.cap is not None:
            self.cap.release()
        self.cap = None
        self.active = False

    # Backward-compatible aliases
    stopCapture = close
    stop_stream = close