from __future__ import annotations

from PyQt6.QtCore import pyqtSignal

from src.applications.base.broker_subscription_mixin import SignalBridge
from src.shared_contracts.events.vision_events import VisionTopics


class _DashboardCameraBridge(SignalBridge):
    frame_ready = pyqtSignal(object)


class DashboardCameraFeedMixin:
    """
    Shared dashboard camera-feed wiring.

    Assumptions:
    - controller has `_view`
    - controller has either `_sub(topic, callback)` or `_subscribe(topic, callback)`
    - view exposes `set_trajectory_image(image)`
    """

    def _init_dashboard_camera_feed(self) -> None:
        self._dashboard_camera_bridge = _DashboardCameraBridge()
        self._dashboard_camera_bridge.frame_ready.connect(self._on_dashboard_camera_frame)

    def _subscribe_dashboard_camera_feed(self) -> None:
        subscribe = getattr(self, "_sub", None) or getattr(self, "_subscribe", None)
        if not callable(subscribe):
            raise RuntimeError(
                f"{self.__class__.__name__} must provide _sub() or _subscribe() to use DashboardCameraFeedMixin"
            )
        subscribe(VisionTopics.LATEST_IMAGE, self._on_dashboard_camera_frame_raw)

    def _on_dashboard_camera_frame_raw(self, message: object) -> None:
        if isinstance(message, dict):
            image = message.get("image")
            if image is not None:
                self._dashboard_camera_bridge.frame_ready.emit(message)
            return
        if message is not None:
            self._dashboard_camera_bridge.frame_ready.emit({"image": message})

    def _on_dashboard_camera_frame(self, image: object) -> None:
        if not self._dashboard_view_ok():
            return
        setter = getattr(self._view, "set_trajectory_image", None)
        if callable(setter):
            setter(image)

    def _dashboard_view_ok(self) -> bool:
        guard = getattr(self, "_view_ok", None)
        if callable(guard):
            return bool(guard())
        try:
            _ = self._view.isVisible()
            return True
        except RuntimeError:
            return False
