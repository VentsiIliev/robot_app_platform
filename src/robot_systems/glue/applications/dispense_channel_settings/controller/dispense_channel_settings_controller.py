from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtSignal

from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin, SignalBridge
from src.applications.base.i_application_controller import IApplicationController
from src.engine.core.i_messaging_service import IMessagingService
from src.shared_contracts.events.weight_events import CellStateEvent, WeightReading, WeightTopics
from src.robot_systems.glue.applications.dispense_channel_settings.model.dispense_channel_settings_model import (
    DispenseChannelSettingsModel,
)
from src.robot_systems.glue.applications.dispense_channel_settings.view.dispense_channel_settings_view import (
    DispenseChannelSettingsView,
)


class _Bridge(SignalBridge):
    weight_updated = pyqtSignal(str, float)
    state_updated = pyqtSignal(str, str)


class DispenseChannelSettingsController(IApplicationController, BrokerSubscriptionMixin):
    def __init__(
        self,
        model: DispenseChannelSettingsModel,
        view: DispenseChannelSettingsView,
        broker: IMessagingService,
    ):
        BrokerSubscriptionMixin.__init__(self)
        self._model = model
        self._view = view
        self._broker = broker
        self._active = False
        self._logger = logging.getLogger(self.__class__.__name__)
        self._bridge = _Bridge()
        self._bridge.weight_updated.connect(self._view.set_channel_weight)
        self._bridge.state_updated.connect(self._view.set_channel_state)

    def load(self) -> None:
        self._active = True
        definitions = self._model.load()
        for definition in definitions:
            flat = self._model.get_channel_flat(definition.id)
            if flat is not None:
                self._view.load_channel(definition.id, flat)
            self._view.set_channel_state(definition.id, "disconnected")

        self._view.save_requested.connect(self._on_save)
        self._view.tare_requested.connect(self._on_tare)
        self._view.pump_on_requested.connect(self._on_pump_on)
        self._view.pump_off_requested.connect(self._on_pump_off)
        self._view.destroyed.connect(self.stop)
        self._subscribe_all()

    def stop(self) -> None:
        self._active = False
        self._unsubscribe_all()

    def _subscribe_all(self) -> None:
        for definition in self._model.load():
            self._subscribe(WeightTopics.reading(definition.weight_cell_id), self._on_weight_reading)
            self._subscribe(WeightTopics.state(definition.weight_cell_id), self._on_state_changed)

    def _on_weight_reading(self, reading: WeightReading) -> None:
        channel_id = self._model.get_channel_for_cell_id(reading.cell_id)
        if channel_id is not None:
            self._bridge.weight_updated.emit(channel_id, reading.value)

    def _on_state_changed(self, event: CellStateEvent) -> None:
        channel_id = self._model.get_channel_for_cell_id(event.cell_id)
        if channel_id is not None:
            self._bridge.state_updated.emit(channel_id, event.state.value)

    def _on_save(self, channel_id: str, flat: dict) -> None:
        if not self._active:
            return
        try:
            self._model.save(channel_id, flat)
        except Exception:
            self._logger.exception("Failed to save channel %s", channel_id)

    def _on_tare(self, channel_id: str) -> None:
        if not self._active:
            return
        try:
            self._model.tare(channel_id)
        except Exception:
            self._logger.exception("Failed to tare channel %s", channel_id)

    def _on_pump_on(self, channel_id: str) -> None:
        if not self._active:
            return
        try:
            self._model.start_pump_test(channel_id)
        except Exception:
            self._logger.exception("Failed to start pump test for channel %s", channel_id)

    def _on_pump_off(self, channel_id: str) -> None:
        if not self._active:
            return
        try:
            self._model.stop_pump_test(channel_id)
        except Exception:
            self._logger.exception("Failed to stop pump test for channel %s", channel_id)
