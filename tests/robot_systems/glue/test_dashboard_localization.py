import unittest
from pathlib import Path
from unittest.mock import MagicMock

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication

from src.engine.localization.localization_service import LocalizationService
from src.robot_systems.glue.applications.dashboard import ACTION_BUTTONS
from src.robot_systems.glue.applications.dashboard.config import GlueDashboardConfig
from src.robot_systems.glue.applications.dashboard.controller.glue_dashboard_controller import GlueDashboardController
from src.robot_systems.glue.applications.dashboard.view.glue_dashboard_view import GlueDashboardView
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

    def test_dashboard_buttons_start_translated_on_initial_load(self):
        self._service.set_language("bg")
        view = GlueDashboardView(
            config=GlueDashboardConfig(),
            action_buttons=ACTION_BUTTONS,
            cards=[],
        )
        model = MagicMock()
        model.get_process_state.return_value = "idle"
        model.get_cell_glue_type.return_value = None
        model.get_cell_connection_state.return_value = "unknown"
        broker = MagicMock()

        controller = GlueDashboardController(model, view, broker)
        controller.load()

        self.assertEqual(view._dashboard.control_buttons.start_btn.text(), "Старт")
        self.assertEqual(view._dashboard.control_buttons.stop_btn.text(), "Стоп")
        self.assertEqual(view._dashboard.control_buttons.pause_btn.text(), "Пауза")
        self.assertEqual(view._dashboard._action_buttons["reset_errors"].text(), "Нулирай грешките")
        self.assertEqual(view._dashboard._action_buttons["mode_toggle"].text(), "Вземи и пръскай")
        self.assertEqual(view._dashboard._action_buttons["clean"].text(), "Почистване")
