import unittest
from pathlib import Path

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication

from src.engine.localization.localization_service import LocalizationService
from src.robot_systems.glue.applications.dashboard.ui.system_status_widget import SystemStatusWidget
from src.robot_systems.glue.applications.dashboard.ui.widgets.GlueMeterCard import GlueMeterCard


_TRANSLATIONS_DIR = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "robot_systems"
    / "glue"
    / "storage"
    / "translations"
)


class TestDashboardLocalization(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._service = LocalizationService(str(_TRANSLATIONS_DIR))
        self._service.set_language("en")

    def test_glue_meter_card_retranslates_title_and_state_tooltip(self):
        card = GlueMeterCard("Cell 1", 1)
        card.set_state("connected")

        self._service.set_language("bg")
        QApplication.sendEvent(card, QEvent(QEvent.Type.LanguageChange))

        self.assertEqual(card.title_label.text(), "Клетка 1")
        self.assertEqual(card.state_indicator.toolTip(), "Свързано")

    def test_system_status_widget_retranslates_labels_and_badges(self):
        widget = SystemStatusWidget()
        widget.set_process_state("running")
        widget.set_system_state("idle")

        self._service.set_language("bg")
        QApplication.sendEvent(widget, QEvent(QEvent.Type.LanguageChange))

        self.assertEqual(widget._process_label.text(), "Процес")
        self.assertEqual(widget._warning_label.text(), "Предупреждение")
        self.assertEqual(widget._process_badge.text(), "Работи")
        self.assertEqual(widget._system_badge.text(), "Изчакване")
