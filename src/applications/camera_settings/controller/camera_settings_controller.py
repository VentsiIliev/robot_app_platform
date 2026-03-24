import logging

from PyQt6.QtCore import pyqtSignal

from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin, SignalBridge
from src.applications.base.i_application_controller import IApplicationController
from src.applications.camera_settings.mapper import CameraSettingsMapper
from src.applications.camera_settings.model.camera_settings_model import CameraSettingsModel
from src.applications.camera_settings.view.camera_settings_view import CameraSettingsView
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(SignalBridge):
    camera_frame    = pyqtSignal(object)
    threshold_frame = pyqtSignal(object)
    vision_state    = pyqtSignal(str)


_TOGGLE_KEYS = {
    "contour_detection", "draw_contours", "gaussian_blur",
    "dilate_enabled", "erode_enabled", "brightness_auto",
    "aruco_enabled", "aruco_flip_image",
}


class CameraSettingsController(IApplicationController, BrokerSubscriptionMixin):

    def __init__(self, model: CameraSettingsModel, view: CameraSettingsView,
                 messaging: IMessagingService):
        BrokerSubscriptionMixin.__init__(self)
        self._model  = model
        self._view   = view
        self._broker = messaging
        self._bridge = _Bridge()
        self._active = False
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        self._active = True
        self._wire_bridge()
        self._connect_signals()
        self._setup_subscriptions()
        settings = self._model.load()
        self._view.settings_view.set_values(CameraSettingsMapper.to_flat_dict(settings))
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        self._unsubscribe_all()

    # ── Bridge ────────────────────────────────────────────────────────

    def _wire_bridge(self) -> None:
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.threshold_frame.connect(self._on_threshold_frame)
        self._bridge.vision_state.connect(self._on_vision_state)

    # ── Broker → Bridge (background thread) ──────────────────────────

    def _setup_subscriptions(self) -> None:
        self._subscribe(VisionTopics.LATEST_IMAGE,    self._on_latest_image_raw)
        self._subscribe(VisionTopics.THRESHOLD_IMAGE, self._on_threshold_image_raw)
        self._subscribe(VisionTopics.SERVICE_STATE,   self._on_service_state_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_threshold_image_raw(self, msg) -> None:
        if msg is not None:
            self._bridge.threshold_frame.emit(msg)

    def _on_service_state_raw(self, state) -> None:
        self._bridge.vision_state.emit(str(state))

    # ── Bridge slots (main thread) ────────────────────────────────────

    def _on_camera_frame(self, frame) -> None:
        if self._active:
            self._view.update_camera_view(frame)

    def _on_threshold_frame(self, frame) -> None:
        if self._active:
            self._view.update_threshold_view(frame)

    def _on_vision_state(self, state: str) -> None:
        if self._active:
            self._view.set_vision_state(state)

    # ── View → Model ──────────────────────────────────────────────────

    def _connect_signals(self) -> None:
        self._view.save_requested.connect(self._on_save)
        self._view.value_changed_signal.connect(self._on_value_changed)
        self._view.raw_mode_toggled.connect(self._model.set_raw_mode)

    def _on_value_changed(self, key: str, value, component_name: str) -> None:
        if key in _TOGGLE_KEYS:
            self._on_save(self._view.settings_view.get_values())

    def _on_save(self, flat: dict) -> None:
        settings = CameraSettingsMapper.from_flat_dict(flat, self._model.current_settings)
        self._model.save(settings)
