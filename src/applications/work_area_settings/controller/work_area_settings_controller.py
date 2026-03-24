from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtSignal

from src.applications.base.broker_subscription_mixin import (
    BrokerSubscriptionMixin,
    SignalBridge,
)
from src.applications.base.i_application_controller import IApplicationController
from src.applications.work_area_settings.model.work_area_settings_model import (
    WorkAreaSettingsModel,
)
from src.applications.work_area_settings.view.work_area_settings_view import (
    WorkAreaSettingsView,
)
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.vision_events import VisionTopics


class _Bridge(SignalBridge):
    camera_frame = pyqtSignal(object)
    vision_state = pyqtSignal(str)


class WorkAreaSettingsController(IApplicationController, BrokerSubscriptionMixin):
    def __init__(
        self,
        model: WorkAreaSettingsModel,
        view: WorkAreaSettingsView,
        messaging: IMessagingService,
    ):
        BrokerSubscriptionMixin.__init__(self)
        self._model = model
        self._view = view
        self._broker = messaging
        self._bridge = _Bridge()
        self._active = False
        self._logger = logging.getLogger(self.__class__.__name__)

    def load(self) -> None:
        self._active = True
        self._wire_bridge()
        self._connect_signals()
        self._setup_subscriptions()
        self._load_all_areas()
        active_area_id = self._model.get_active_work_area_id()
        if active_area_id:
            self._view.set_current_work_area_id(active_area_id)
        self._view.destroyed.connect(self.stop)

    def stop(self) -> None:
        self._active = False
        self._unsubscribe_all()

    def _wire_bridge(self) -> None:
        self._bridge.camera_frame.connect(self._on_camera_frame)
        self._bridge.vision_state.connect(self._on_vision_state)

    def _setup_subscriptions(self) -> None:
        self._subscribe(VisionTopics.LATEST_IMAGE, self._on_latest_image_raw)
        self._subscribe(VisionTopics.SERVICE_STATE, self._on_service_state_raw)

    def _on_latest_image_raw(self, msg) -> None:
        if isinstance(msg, dict):
            frame = msg.get("image")
            if frame is not None:
                self._bridge.camera_frame.emit(frame)

    def _on_service_state_raw(self, state) -> None:
        self._bridge.vision_state.emit(str(state))

    def _on_camera_frame(self, frame) -> None:
        if self._active:
            self._view.update_camera_view(frame)

    def _on_vision_state(self, state: str) -> None:
        if self._active:
            self._view.set_vision_state(state)

    def _connect_signals(self) -> None:
        self._view.work_area_changed.connect(self._on_work_area_changed)
        self._view.save_area_requested.connect(self._on_save_area)

    def _on_work_area_changed(self, area_id: str) -> None:
        if self._active:
            self._model.set_active_work_area_id(area_id)

    def _on_save_area(self, area_key: str) -> None:
        if not self._active:
            return
        points = self._view.get_area_corners(area_key)
        if len(points) != 4:
            self._logger.warning("Area %s has %d corners, need 4 to save", area_key, len(points))
            return
        ok, msg = self._model.save_work_area(area_key, points)
        self._logger.info("Save work area '%s': %s — %s", area_key, ok, msg)

    def _load_all_areas(self) -> None:
        for definition in self._view.work_area_definitions:
            if definition.supports_detection_roi:
                area_key = definition.detection_area_key()
                points = self._model.get_work_area(area_key)
                if points:
                    self._view.set_area_corners(area_key, points)
            if definition.supports_brightness_roi:
                area_key = definition.brightness_area_key()
                points = self._model.get_work_area(area_key)
                if points:
                    self._view.set_area_corners(area_key, points)
