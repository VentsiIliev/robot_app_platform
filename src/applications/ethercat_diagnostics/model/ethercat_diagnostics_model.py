from __future__ import annotations

from src.applications.base.i_application_model import IApplicationModel
from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    EthercatDiagnosticsSnapshot,
    IEthercatDiagnosticsService,
)


class EthercatDiagnosticsModel(IApplicationModel):
    def __init__(self, service: IEthercatDiagnosticsService) -> None:
        self._service = service
        self._snapshot = EthercatDiagnosticsSnapshot()

    def load(self) -> EthercatDiagnosticsSnapshot:
        self._snapshot = self._service.refresh()
        return self._snapshot

    def save(self, *args, **kwargs) -> None:
        return None

    def refresh(self) -> EthercatDiagnosticsSnapshot:
        self._snapshot = self._service.refresh()
        return self._snapshot

    def supports_reset_errors(self) -> bool:
        return self._service.supports_reset_errors()

    def reset_errors(self) -> tuple[bool, str]:
        return self._service.reset_errors()
