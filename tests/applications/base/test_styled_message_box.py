import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox, QPushButton

from src.applications.base.styled_message_box import (
    DialogAction, make_warning, show_warning,
)


class TestStyledMessageBox(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_action_warning_returns_chosen_button_and_allows_optional_sections(self) -> None:
        actions = (
            DialogAction("retry", "Scan again", primary=True),
            DialogAction("dismiss", "Dismiss", full_width=True),
        )
        def choose_retry() -> None:
            dialog = QApplication.activeModalWidget()
            self.assertIsNone(dialog.findChild(QPushButton, "warningAction_open_library"))
            self.assertIsNone(dialog.findChild(QLabel, "warningGuidance"))
            dialog.findChild(QPushButton, "warningAction_retry").click()

        QTimer.singleShot(0, choose_retry)
        selected = show_warning(
            None, "Workpiece not recognized", "No match",
            heading="PAINTING STOPPED", actions=actions,
        )

        self.assertEqual(selected, "retry")

    def test_plain_warning_keeps_message_box_api(self) -> None:
        self.assertIsInstance(make_warning(None, "Warning", "Text"), QMessageBox)


if __name__ == "__main__":
    unittest.main()
