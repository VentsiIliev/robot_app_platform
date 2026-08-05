from __future__ import annotations

import logging

from src.applications.base.background_worker import BackgroundWorker
from src.applications.base.i_application_controller import IApplicationController
from src.applications.ethercat_diagnostics.model.ethercat_diagnostics_model import (
    EthercatDiagnosticsModel,
)
from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    EthercatDiagnosticsSnapshot,
)
from src.applications.ethercat_diagnostics.view.ethercat_diagnostics_view import (
    EthercatDiagnosticsView,
)


class EthercatDiagnosticsController(IApplicationController, BackgroundWorker):
    def __init__(self, model: EthercatDiagnosticsModel, view: EthercatDiagnosticsView) -> None:
        BackgroundWorker.__init__(self)
        self._model = model
        self._view = view
        self._logger = logging.getLogger(self.__class__.__name__)

        self._view.refresh_requested.connect(self._on_refresh)
        self._view.reset_errors_requested.connect(self._on_reset_errors)
        self._view.destroyed.connect(self.stop)

    def load(self) -> None:
        self._view.set_reset_enabled(self._model.supports_reset_errors())
        self._on_refresh()

    def stop(self) -> None:
        self._stop_threads()

    def _on_refresh(self) -> None:
        self._view.set_busy(True)
        self._run_in_thread(
            fn=self._model.refresh,
            on_done=self._on_snapshot,
            on_error=self._on_error,
        )

    def _on_reset_errors(self) -> None:
        self._view.set_busy(True)
        self._run_in_thread(
            fn=self._model.reset_errors,
            on_done=self._on_reset_done,
            on_error=self._on_error,
        )

    def _on_snapshot(self, snapshot: EthercatDiagnosticsSnapshot) -> None:
        self._view.set_busy(False)
        self._view.set_snapshot(snapshot)

    def _on_reset_done(self, result: tuple[bool, str]) -> None:
        ok, message = result
        self._view.set_status_message(message, ok=ok)
        self._on_refresh()

    def _on_error(self, message: str) -> None:
        self._logger.error("EtherCAT diagnostics failed: %s", message)
        self._view.set_busy(False)
        self._view.set_status_message(message, ok=False)
