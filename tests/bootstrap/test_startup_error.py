import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.bootstrap.startup_error import report_startup_error, _show_error_dialog


class StartupErrorTests(unittest.TestCase):
    def test_error_is_saved_and_presented_without_a_terminal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "logs"
            with patch("src.bootstrap.startup_error._show_error_dialog") as dialog, contextlib.redirect_stderr(io.StringIO()):
                report_startup_error(ValueError("Unsupported strategy"), root)
            self.assertIn("ValueError: Unsupported strategy", (root / "last-startup-error.log").read_text())
            error, details = dialog.call_args.args
            self.assertEqual("Unsupported strategy", error)
            self.assertIn(str(root / "last-startup-error.log"), details)

    def test_unwritable_log_does_not_prevent_the_dialog(self):
        with patch("pathlib.Path.mkdir", side_effect=PermissionError("read-only")), patch("src.bootstrap.startup_error._show_error_dialog") as dialog, contextlib.redirect_stderr(io.StringIO()):
            report_startup_error(ValueError("Invalid settings"), Path("unused"))
        self.assertIn("Could not save error log", dialog.call_args.args[1])

    def test_dialog_displays_plain_error_and_expandable_details(self):
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication([])
        shown = []
        def capture(dialog):
            shown.append((dialog.informativeText(), dialog.detailedText(), dialog.windowTitle()))
            return 0
        with patch.object(QMessageBox, "exec", capture):
            _show_error_dialog("Invalid strategy", "Traceback and log path")
        self.assertEqual([("Invalid strategy", "Traceback and log path", "Platform could not start")], shown)
