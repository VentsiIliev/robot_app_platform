from __future__ import annotations

import unittest

from src.applications.ethercat_diagnostics.service.ethercat_diagnostics_application_service import (
    EthercatDiagnosticsApplicationService,
)


class _GenericProvider:
    def get_ethercat_diagnostics(self):
        return {
            "master_state": "operational",
            "slaves": [
                {"id": 1, "name": "Drive A", "state": "operational", "online": True},
                {"id": 2, "name": "Drive B", "state": "safe_op", "online": True, "error": "not op"},
            ],
        }


class _DriveStatusProvider:
    def get_drive_status(self):
        return {
            "success": True,
            "state": "DISABLED",
            "motion_allowed_by_drive_enable": False,
            "status_state": ["switched_on", "operation_enabled"],
            "statusword": [4787, 4663],
        }


class _ErrorProvider:
    def get_drive_status(self):
        return {
            "success": False,
            "error": "Failed to upload SDO: Invalid argument",
        }


class TestEthercatDiagnosticsService(unittest.TestCase):
    def test_normalizes_generic_master_slaves(self) -> None:
        snapshot = EthercatDiagnosticsApplicationService(_GenericProvider()).refresh()

        self.assertEqual(snapshot.master_state, "operational")
        self.assertEqual(len(snapshot.slaves), 2)
        self.assertEqual(snapshot.slaves[0].name, "Drive A")
        self.assertTrue(snapshot.slaves[0].operational)
        self.assertFalse(snapshot.slaves[1].operational)
        self.assertEqual(snapshot.slaves[1].error, "not op")

    def test_normalizes_drive_status_fallback_as_slaves(self) -> None:
        snapshot = EthercatDiagnosticsApplicationService(_DriveStatusProvider()).refresh()

        self.assertEqual(snapshot.master_state, "DISABLED")
        self.assertEqual(len(snapshot.slaves), 2)
        self.assertEqual(snapshot.slaves[0].statusword, 4787)
        self.assertFalse(snapshot.slaves[0].operational)
        self.assertTrue(snapshot.slaves[1].operational)

    def test_reports_provider_error_payload(self) -> None:
        snapshot = EthercatDiagnosticsApplicationService(_ErrorProvider()).refresh()

        self.assertEqual(snapshot.master_state, "error")
        self.assertEqual(snapshot.master_message, "Failed to upload SDO: Invalid argument")


if __name__ == "__main__":
    unittest.main()
