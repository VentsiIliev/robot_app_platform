from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from src.applications.ethercat_diagnostics.service.igh_ethercat_diagnostics_service import (
    IghEthercatDiagnosticsService,
)


class TestIghEthercatDiagnosticsService(unittest.TestCase):
    def test_parse_slaves_normal_output(self) -> None:
        slaves = IghEthercatDiagnosticsService.parse_slaves(
            "\n".join(
                [
                    "0  0:0  OP     +  EL1008 8K. Dig. Input 24V",
                    "1  0:1  SAFEOP E  EL2008 8K. Dig. Output 24V",
                ]
            )
        )

        self.assertEqual(len(slaves), 2)
        self.assertEqual(slaves[0].slave_id, 0)
        self.assertEqual(slaves[0].state, "OP")
        self.assertTrue(slaves[0].operational)
        self.assertEqual(slaves[1].details["error_flag"], "E")
        self.assertFalse(slaves[1].operational)
        self.assertIn("configuration failed", slaves[1].error)

    def test_refresh_runs_master_slaves_and_crc(self) -> None:
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            if command[-1] == "slaves":
                stdout = "0  0:0  OP  +  Drive A\n1  0:1  PREOP  +  Drive B\n"
            elif command[-1] == "crc":
                stdout = "0 0 0 0\n"
            else:
                stdout = "Master0\n"
            return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

        with patch("src.applications.ethercat_diagnostics.service.igh_ethercat_diagnostics_service.shutil.which", return_value="/usr/bin/ethercat"):
            snapshot = IghEthercatDiagnosticsService(runner=runner, master="0").refresh()

        self.assertEqual(
            calls,
            [
                ["ethercat", "--master", "0", "master"],
                ["ethercat", "--master", "0", "slaves"],
                ["ethercat", "--master", "0", "crc"],
            ],
        )
        self.assertEqual(snapshot.master_state, "not_ready")
        self.assertEqual(len(snapshot.slaves), 2)
        self.assertIn("not OP", snapshot.master_message)

    def test_reset_errors_uses_crc_reset(self) -> None:
        calls = []

        def runner(command, **kwargs):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with patch("src.applications.ethercat_diagnostics.service.igh_ethercat_diagnostics_service.shutil.which", return_value="/usr/bin/ethercat"):
            ok, message = IghEthercatDiagnosticsService(runner=runner).reset_errors()

        self.assertTrue(ok)
        self.assertEqual(message, "EtherCAT CRC/error counters reset")
        self.assertEqual(calls, [["ethercat", "crc", "reset"]])


if __name__ == "__main__":
    unittest.main()
