import unittest
from types import SimpleNamespace

from src.bootstrap.run_main import _startup_splash_stage_text


class TestStartupSplashStatusText(unittest.TestCase):

    def test_disconnected_state_shows_connecting_stage(self):
        snapshot = SimpleNamespace(
            state="disconnected",
            extra={
                "readiness_state": "disconnected",
                "readiness_note": "Robot bridge is disconnected",
            },
        )

        self.assertEqual(_startup_splash_stage_text(snapshot), "Connecting to robot runtime")

    def test_disabled_drives_show_enabling_stage(self):
        snapshot = SimpleNamespace(
            state="idle",
            extra={
                "readiness_state": "drive_not_ready",
                "readiness_note": "Robot drives are disabled",
            },
        )

        self.assertEqual(_startup_splash_stage_text(snapshot), "Enabling robot drives")

    def test_ethercat_drive_warning_shows_communication_stage(self):
        snapshot = SimpleNamespace(
            state="idle",
            extra={
                "readiness_state": "drive_not_ready",
                "readiness_note": "EtherCAT communication error",
            },
        )

        self.assertEqual(_startup_splash_stage_text(snapshot), "Checking EtherCAT communication")

    def test_tool_mismatch_shows_tool_configuration_stage(self):
        snapshot = SimpleNamespace(
            state="tool_mismatch",
            extra={
                "readiness_state": "tool_mismatch",
                "readiness_note": "Configured robot tool could not be activated",
            },
        )

        self.assertEqual(_startup_splash_stage_text(snapshot), "Configuring robot tool")

    def test_unknown_state_uses_neutral_readiness_stage(self):
        snapshot = SimpleNamespace(state="unknown", extra={})

        self.assertEqual(_startup_splash_stage_text(snapshot), "Waiting for robot readiness")


if __name__ == "__main__":
    unittest.main()
