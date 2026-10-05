import unittest
import os
import subprocess
import sys
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from src.applications.network_settings.controller.network_settings_controller import (
    NetworkSettingsController,
)
from src.applications.network_settings.service.network_settings_service import (
    NetworkSettingsService,
)
from src.applications.network_settings.view.network_settings_view import (
    NetworkSettingsView, _IPv4Dialog,
)


class NetworkSettingsServiceTests(unittest.TestCase):
    def test_linux_wifi_ipv4_uses_active_connection(self) -> None:
        backend = MagicMock()
        backend.get_devices.return_value = [
            {"device": "wlan0", "type": "wifi", "state": "connected", "connection": "Workshop"},
        ]
        backend.get_connection_settings.return_value = {"mode": "auto"}
        service = NetworkSettingsService(backend=backend, platform="linux")

        self.assertEqual(
            service.get_wifi_ipv4(),
            {"target": "Workshop", "settings": {"mode": "auto"}},
        )

    def test_invalid_manual_ipv4_does_not_run_network_command(self) -> None:
        backend = MagicMock()
        service = NetworkSettingsService(backend=backend, platform="linux")

        with self.assertRaisesRegex(ValueError, "valid IPv4"):
            service.apply_ipv4("Workshop", {
                "mode": "manual", "ip": "999.1.1.1", "prefix": "24",
                "gateway": "", "dns": "",
            })

        backend.apply_settings.assert_not_called()

    def test_secure_wifi_requires_password_before_backend_call(self) -> None:
        backend = MagicMock()
        service = NetworkSettingsService(backend=backend, platform="linux")

        with self.assertRaisesRegex(ValueError, "password"):
            service.connect_wifi("Workshop", "", True)

        backend.connect_wifi.assert_not_called()

    def test_remote_support_uses_only_local_controller_client(self) -> None:
        client = MagicMock()
        client.status.return_value = {"enabled": False, "active": False}
        client.set_enabled.return_value = {"enabled": True, "active": True}
        service = NetworkSettingsService(
            backend=MagicMock(), platform="linux", remote_support_client=client,
        )

        self.assertEqual(service.get_remote_support_status(), client.status.return_value)
        self.assertEqual(service.set_remote_support_enabled(True), client.set_enabled.return_value)
        client.set_enabled.assert_called_once_with(True)


class NetworkSettingsViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_wifi_actions_follow_selected_connection(self) -> None:
        view = NetworkSettingsView()
        view.set_wifi_networks([
            {"ssid": "Workshop", "signal": "80", "secure": True, "connected": True},
            {"ssid": "Guest", "signal": "60", "secure": False, "connected": False},
        ])
        view._wifi_list.setCurrentRow(0)
        self.assertFalse(view._buttons["wifi"]["connect"].isEnabled())
        self.assertTrue(view._buttons["wifi"]["disconnect"].isEnabled())
        self.assertTrue(view._buttons["wifi"]["ipv4"].isEnabled())

        view._wifi_list.setCurrentRow(1)
        self.assertTrue(view._buttons["wifi"]["connect"].isEnabled())
        self.assertFalse(view._buttons["wifi"]["ipv4"].isEnabled())

    def test_ipv4_dialog_uses_shared_touch_prefix_field(self) -> None:
        dialog = _IPv4Dialog({"mode": "manual", "ip": "192.168.1.10", "prefix": "24"})
        self.assertIsInstance(dialog._prefix, KeyboardNumberField)
        self.assertEqual(dialog.settings()["prefix"], "24")

    def test_controller_schedules_actions_without_blocking_view(self) -> None:
        model = MagicMock()
        view = NetworkSettingsView()
        controller = NetworkSettingsController(model, view)
        controller._run_in_thread = MagicMock()

        controller._connect_wired("eth0")

        self.assertTrue(controller._busy["wired"])
        controller._run_in_thread.assert_called_once()
        model.connect_wired.assert_not_called()

    def test_remote_switch_waits_for_confirmed_state(self) -> None:
        view = NetworkSettingsView()
        self.assertFalse(view._remote_switch.isEnabled())
        view.set_remote_support_status({"enabled": False, "active": False})
        self.assertTrue(view._remote_switch.isEnabled())
        received = []
        view.remote_support_requested.connect(received.append)

        view._remote_switch.click()

        self.assertEqual(received, [True])
        self.assertFalse(view._remote_switch.isChecked())
        view.set_busy("remote", True)
        self.assertFalse(view._remote_switch.isEnabled())
        view.set_remote_support_status({"enabled": True, "active": True})
        self.assertTrue(view._remote_switch.isChecked())

    def test_remote_mismatch_is_visible(self) -> None:
        view = NetworkSettingsView()
        view.set_remote_support_status({"enabled": False, "active": True})
        self.assertIn("action needed", view._remote_state.text())
        self.assertIn("still active", view._remote_service.text())

    def test_remote_error_replaces_checking_and_can_recover(self) -> None:
        view = NetworkSettingsView()
        controller = NetworkSettingsController(MagicMock(), view)
        controller._on_error("remote", "Remote support controller is not installed")
        self.assertIn("unavailable", view._remote_state.text())
        self.assertIn("not installed", view._remote_service.text())
        self.assertFalse(view._remote_switch.isEnabled())
        controller._remote_support_loaded({"enabled": True, "active": True})
        self.assertTrue(view._remote_switch.isEnabled())
        self.assertTrue(view._remote_switch.isChecked())

    def test_opening_remote_tab_requests_fresh_service_state(self) -> None:
        view = NetworkSettingsView()
        refreshed = MagicMock()
        view.remote_support_refresh_requested.connect(refreshed)
        view._tabs.setCurrentIndex(2)
        refreshed.assert_called_once_with()

    def test_real_workers_finish_without_freezing_startup(self) -> None:
        code = '''
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
from src.applications.network_settings.network_settings_factory import NetworkSettingsFactory
from src.applications.network_settings.service.stub_network_settings_service import StubNetworkSettingsService
app = QApplication([])
view = NetworkSettingsFactory().build(StubNetworkSettingsService())
QTimer.singleShot(500, app.quit)
app.exec()
assert view._remote_switch.isEnabled()
assert not any(view._controller._busy.values())
view.clean_up()
'''
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            timeout=5, env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
