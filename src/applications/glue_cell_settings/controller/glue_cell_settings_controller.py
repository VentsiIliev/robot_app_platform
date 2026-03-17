from __future__ import annotations
import logging

from PyQt6.QtCore import QObject, pyqtSignal

from src.engine.core.i_messaging_service import IMessagingService
from src.applications.base.broker_subscription_mixin import BrokerSubscriptionMixin, SignalBridge
from src.applications.base.i_application_controller import IApplicationController
from src.shared_contracts.events.weight_events import WeightTopics
from src.applications.glue_cell_settings.model.glue_cell_settings_model import GlueCellSettingsModel
from src.applications.glue_cell_settings.view.glue_cell_settings_view import GlueCellSettingsView


class _Bridge(SignalBridge):
    weight_updated = pyqtSignal(int, float)
    state_updated  = pyqtSignal(int, str)


class GlueCellSettingsController(IApplicationController, BrokerSubscriptionMixin):

    def __init__(
        self,
        model:   GlueCellSettingsModel,
        view:    GlueCellSettingsView,
        broker:  IMessagingService,
    ):
        BrokerSubscriptionMixin.__init__(self)
        self._model  = model
        self._view   = view
        self._broker = broker
        self._active = False
        self._logger = logging.getLogger(self.__class__.__name__)
        self._bridge = _Bridge()
        self._bridge.weight_updated.connect(self._view.set_cell_weight)
        self._bridge.state_updated.connect(self._view.set_cell_state)

    def load(self) -> None:
        self._active = True
        config = self._model.load()
        for cell_id in config.get_all_cell_ids():
            flat = self._model.get_cell_flat(cell_id)
            if flat:
                self._view.load_cell(cell_id, flat)
            # set initial state
            self._view.set_cell_state(cell_id, "disconnected")

        self._view.save_requested.connect(self._on_save)
        self._view.tare_requested.connect(self._on_tare)
        self._view.destroyed.connect(self.stop)
        self._subscribe()

    def stop(self) -> None:
        self._active = False
        self._unsubscribe_all()

    # ── Broker → Bridge (background-thread safe) ──────────────────────

    def _subscribe(self) -> None:
        for cell_id in self._model.get_cell_ids():
            self._subscribe(
                WeightTopics.reading(cell_id),
                lambda r, cid=cell_id: self._bridge.weight_updated.emit(cid, r.value),
            )
            self._subscribe(
                WeightTopics.state(cell_id),
                lambda e, cid=cell_id: self._bridge.state_updated.emit(cid, e.state.value),
            )

    # ── View signals → Model ──────────────────────────────────────────

    def _on_save(self, cell_id: int, flat: dict) -> None:
        if not self._active: return
        try:
            self._model.save(cell_id, flat)
            self._logger.info("Cell %s settings saved", cell_id)
        except Exception:
            self._logger.exception("Failed to save cell %s settings", cell_id)

    def _on_tare(self, cell_id: int) -> None:
        if not self._active: return
        try:
            ok = self._model.tare(cell_id)
            self._logger.info("Tare cell %s → %s", cell_id, "ok" if ok else "failed")
        except Exception:
            self._logger.exception("Tare failed for cell %s", cell_id)

