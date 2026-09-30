from __future__ import annotations

from threading import Lock

from PyQt6.QtCore import QTimer

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.camera_settings.model.camera_settings_model import CameraSettingsModel
from src.applications.camera_settings.service.i_camera_settings_service import (
    CameraOrientation,
)
from src.applications.camera_settings.view.camera_devices_widget import CameraDevicesWidget
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import CameraTopics


class CameraDevicesController(
    IApplicationController,
    BackgroundWorker,
):
    """Reusable controller for the camera-role assignment and preview panel."""

    def __init__(
        self,
        model: CameraSettingsModel,
        view: CameraDevicesWidget,
        messaging: IMessagingService,
    ) -> None:
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._broker = messaging
        self._preview_role = "primary_vision"
        self._active = False
        self._preview_visible = False
        self._subscribed_topic: str | None = None
        self._frame_lock = Lock()
        self._latest_frame = None
        self._display_timer = QTimer(view)
        self._display_timer.setInterval(100)
        self._display_timer.timeout.connect(self._display_latest_frame)
        self._view.refresh_requested.connect(self._refresh)
        self._view.save_requested.connect(self._save)
        self._view.preview_requested.connect(self._request_preview)
        self._view.preview_visibility_changed.connect(self._set_preview_visible)

    def load(self) -> None:
        self._active = True
        self._set_preview_visible(self._view.isVisible())
        self._refresh()

    def stop(self) -> None:
        self._active = False
        self._set_preview_visible(False)
        self._stop_threads()

    def _refresh(self) -> None:
        self._run_in_thread(
            fn=self._model.load_camera_devices,
            on_done=self._on_loaded,
            on_error=self._on_error,
        )

    def _on_loaded(self, state) -> None:
        if self._active:
            self._view.set_camera_devices(state)

    def _save(
        self,
        assignments: dict[str, str],
        orientation: dict[str, CameraOrientation],
    ) -> None:
        self._run_in_thread(
            fn=lambda: self._model.save_camera_devices(assignments, orientation),
            on_done=self._on_saved,
            on_error=self._on_error,
        )

    def _on_saved(self, _result) -> None:
        if self._active:
            self._view.set_saved()

    def _request_preview(self, role: str, device: str) -> None:
        del device
        self._preview_role = role
        self._update_subscription()

    def _set_preview_visible(self, visible: bool) -> None:
        self._preview_visible = bool(visible)
        if self._active and self._preview_visible:
            self._display_timer.start()
        else:
            self._display_timer.stop()
        self._update_subscription()

    def _update_subscription(self) -> None:
        topic = (
            CameraTopics.frame(self._preview_role)
            if self._active and self._preview_visible
            else None
        )
        if topic == self._subscribed_topic:
            return
        if self._subscribed_topic is not None:
            self._broker.unsubscribe(self._subscribed_topic, self._on_frame_message)
        with self._frame_lock:
            self._latest_frame = None
        self._subscribed_topic = topic
        if topic is not None:
            self._broker.subscribe(topic, self._on_frame_message)

    def _on_frame_message(self, message) -> None:
        if not isinstance(message, dict):
            return
        frame = message.get("image")
        if frame is not None:
            with self._frame_lock:
                self._latest_frame = frame

    def _display_latest_frame(self) -> None:
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
        if self._active and self._preview_visible and frame is not None:
            self._view.set_preview_frame(frame)

    def _on_error(self, message: str) -> None:
        if self._active:
            self._view.set_error(message)
