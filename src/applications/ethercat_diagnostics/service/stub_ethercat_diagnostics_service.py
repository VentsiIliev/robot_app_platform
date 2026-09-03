from __future__ import annotations

from src.applications.ethercat_diagnostics.service.i_ethercat_diagnostics_service import (
    EthercatDiagnosticsSnapshot,
    EthercatSlaveStatus,
    IEthercatDiagnosticsService,
)


class StubEthercatDiagnosticsService(IEthercatDiagnosticsService):
    def refresh(self) -> EthercatDiagnosticsSnapshot:
        return EthercatDiagnosticsSnapshot(
            master_state="not_ready",
            master_message="One or more slaves are not operational",
            slaves=(
                EthercatSlaveStatus(1, "Axis 1", "operational", True, True, statusword=0x1237),
                EthercatSlaveStatus(2, "Axis 2", "safe_op", True, False, "Waiting for OP", 0x1234),
            ),
            raw={"mode": "stub"},
        )

    def supports_reset_errors(self) -> bool:
        return True

    def reset_errors(self) -> tuple[bool, str]:
        return True, "Stub reset completed"
