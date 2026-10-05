import os
import json
import platform
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication
from src.applications.software_update.software_update_factory import SoftwareUpdateFactory
from src.applications.software_update.service.stub_software_update_service import StubSoftwareUpdateService
from src.applications.software_update.service.software_update_service import SoftwareUpdateService
from src.engine.localization.localization_service import LocalizationService


class SoftwareUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.information = patch('src.applications.software_update.view.software_update_view.QMessageBox.information').start()
        self.critical = patch('src.applications.software_update.view.software_update_view.QMessageBox.critical').start()
        self.addCleanup(patch.stopall)
        self.service = StubSoftwareUpdateService()
        self.view = SoftwareUpdateFactory().build(self.service)
        self.addCleanup(self.view.clean_up)
        self.addCleanup(self.view.deleteLater)

    def wait_done(self):
        deadline = time.monotonic() + 5
        while self.view._controller._busy and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertFalse(self.view._controller._busy)

    def test_download_runs_off_gui_thread_then_updates_buttons(self):
        gui_thread = threading.get_ident()
        threads = []
        original = self.service.download
        def download():
            threads.append(threading.get_ident())
            return original()
        with patch.object(self.service, "download", side_effect=download):
            self.view._download.click()
            self.wait_done()
        self.assertNotEqual(gui_thread, threads[0])
        self.assertTrue(self.view._install.isEnabled())
        self.assertIn("1.1.0", self.view._details.text())

    def test_install_schedules_and_does_not_quit_application(self):
        self.view._controller._downloaded(self.service.download())
        self.view._install.click()
        self.assertTrue(self.service.scheduled)
        self.assertIn("Close the application", self.view._status.text())

    def test_check_displays_available_version(self):
        self.view._check.click()
        self.wait_done()
        self.assertEqual("Version 1.1.0 is available", self.view._status.text())
        self.assertEqual("Version 1.1.0 is available", self.information.call_args.args[2])

    def test_up_to_date_check_shows_a_result_dialog(self):
        with patch.object(self.service, 'check', return_value={'version': '1.0.3', 'available': False}):
            self.view._check.click()
            self.wait_done()
        self.assertEqual('The platform is up to date', self.view._status.text())
        self.assertEqual('The platform is up to date', self.information.call_args.args[2])

    def test_disabled_updates_allow_check_and_show_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "updates.json"
            path.write_text(json.dumps({"enabled": False, "install_root": str(Path(directory) / "installed"),
                                        "repository_url": "https://placeholder.example/", "public_key": None}))
            with patch.dict(os.environ, {"ROBOT_PLATFORM_UPDATE_CONFIG": str(path)}):
                view = SoftwareUpdateFactory().build(SoftwareUpdateService(lambda: True))
                self.addCleanup(view.clean_up)
                self.addCleanup(view.deleteLater)
                self.assertTrue(view._check.isEnabled())
                self.assertFalse(view._download.isEnabled())
                self.assertFalse(view._install.isEnabled())
                view._check.click()
                deadline = time.monotonic() + 5
                while view._controller._busy and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.005)
                self.assertFalse(view._controller._busy)
                self.assertIn("Updates are disabled", view._status.text())
                self.assertIn("Updates are disabled", self.critical.call_args.args[2])
                self.assertTrue(view._check.isEnabled())

    def test_check_with_missing_configuration_reports_its_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with patch.dict(os.environ, {"ROBOT_PLATFORM_UPDATE_CONFIG": str(path)}):
                service = SoftwareUpdateService(lambda: True)
                self.assertFalse(service.get_status()["enabled"])
                with self.assertRaisesRegex(RuntimeError, "Update configuration is missing") as raised:
                    service.check()
                self.assertIn(str(path), str(raised.exception))

    def test_check_reads_local_feed_and_displays_available_version(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feed = root / 'feed/stable'
            feed.mkdir(parents=True)
            (feed / 'latest.json').write_text(json.dumps({
                'format': 1, 'product': 'paint-robot', 'version': '1.2.0',
                'architecture': platform.machine(), 'os': 'ubuntu-24.04',
                'storage_schema': 1, 'channel': 'stable',
                'archive': 'release.tar.gz', 'sha256': '0' * 64,
            }))
            config = root / 'updates.json'
            config.write_text(json.dumps({'enabled': True, 'public_key': None,
                                          'repository_url': str(feed.parent), 'install_root': str(root / 'installed')}))
            with patch.dict(os.environ, {'ROBOT_PLATFORM_UPDATE_CONFIG': str(config)}), patch('platform.freedesktop_os_release', return_value={'ID': 'ubuntu', 'VERSION_ID': '24.04'}):
                view = SoftwareUpdateFactory().build(SoftwareUpdateService(lambda: True))
                self.addCleanup(view.clean_up)
                self.addCleanup(view.deleteLater)
                view._check.click()
                deadline = time.monotonic() + 5
                while view._controller._busy and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.005)
                self.assertFalse(view._controller._busy)
                self.assertEqual('Version 1.2.0 is available', view._status.text())

    def test_previous_update_failure_is_displayed_after_restart(self):
        details = self.service.get_status()
        details["result"] = {"status": "failed", "message": "Migration failed"}
        with patch.object(self.service, "get_status", return_value=details):
            self.view._controller.load()
        self.assertEqual("Migration failed", self.view._status.text())

    def test_process_gate_rejects_running_process(self):
        def running(): return False
        service = SoftwareUpdateService(running)
        with self.assertRaisesRegex(RuntimeError, "Stop the production process"):
            service.schedule_installation()

    def test_initial_bulgarian_and_runtime_switch_preserve_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            localization = LocalizationService("src/applications/software_update/localization", state_file=str(Path(temporary) / "language.json"))
            localization.set_language("bg")
            localized = SoftwareUpdateFactory().build(StubSoftwareUpdateService())
            self.addCleanup(localized.clean_up)
            self.addCleanup(localized.deleteLater)
            self.assertEqual("Актуализация на софтуера", localized._title.text())
            localized.set_status("Version {version} is available", version="1.1.0")
            self.assertEqual("Налична е версия 1.1.0", localized._status.text())
            localization.set_language("en")
            self.app.processEvents()
            self.assertEqual("Software Update", localized._title.text())
            self.assertEqual("Version 1.1.0 is available", localized._status.text())
            self.app.removeTranslator(localization._current_translator)


if __name__ == "__main__":
    unittest.main()
