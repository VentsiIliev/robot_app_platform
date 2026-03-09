import requests
from urllib.parse import urlparse

from src.engine.vision.implementation.plvision.PLVision.Camera import Camera


class RemoteCamera(Camera):
    """
    Camera subclass for MJPEG HTTP streams.
    Delegates all capture and exposure control to Camera,
    which already handles http:// device strings via CAP_FFMPEG.
    """

    def __init__(self, url: str, width=None, height=None, fps=None):
        super().__init__(
            device=url,
            width=width or 1280,
            height=height or 720,
            fps=fps,
        )
        self.url: str = url
        parsed = urlparse(url)
        self._base_url: str = f"{parsed.scheme}://{parsed.netloc}"
        if not self.active:
            raise RuntimeError(f"Failed to open remote camera at {url}")

    def set_auto_exposure(self, enabled: bool):
        """
        Override Camera.set_auto_exposure — skips the stop/start stream cycle
        that causes SIGSEGV on FFMPEG HTTP streams. Sends an HTTP request to
        the camera server instead.
        """
        if not self.active or self.cap is None:
            return
        try:
            value = "true" if enabled else "false"
            url = f"{self._base_url}/set_auto_exposure?value={value}"
            r = requests.get(url, timeout=2)
            if r.status_code != 200:
                print("Failed to set auto exposure:", r.text)
        except Exception:
            import traceback
            traceback.print_exc()
