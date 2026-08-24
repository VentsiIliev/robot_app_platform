from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QEvent
from PyQt6.QtWidgets import QApplication

from src.applications.base.robot_jog_widget import RobotJogWidget


class TestRobotJogWidgetLocalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls._app = QApplication.instance() or QApplication([])

    def test_initial_render_uses_stable_translation_context(self) -> None:
        translations = {
            "Cartesian": "Декартово",
            "Joint": "Стави",
            "Current Position": "Текуща позиция",
            "Invert Z": "Обърни Z",
            "Mode": "Режим",
            "Step": "Стъпка",
        }

        with patch(
            "src.applications.base.robot_jog_widget.QCoreApplication.translate",
            side_effect=lambda context, text: translations.get(text, text)
            if context == "RobotJogWidget"
            else text,
        ):
            widget = RobotJogWidget()

        self.assertEqual(widget._tabs.tabText(0), "Декартово")
        self.assertEqual(widget._tabs.tabText(1), "Стави")
        self.assertEqual(widget._position_title_label.text(), "Текуща позиция")
        self.assertEqual(widget._invert_z_btn.text(), "⇅  Обърни Z")
        self.assertEqual(widget._mode_label.text(), "Режим:")
        self.assertEqual(widget._step_mode_btn.text(), "Стъпка")

    def test_language_change_retranslates_dynamic_mode_labels(self) -> None:
        widget = RobotJogWidget()
        widget._servo_mode_btn.click()
        translations = {
            "Linear Speed": "Линейна скорост",
            "Rotation Speed": "Скорост на въртене",
        }

        with patch(
            "src.applications.base.robot_jog_widget.QCoreApplication.translate",
            side_effect=lambda _context, text: translations.get(text, text),
        ):
            widget.changeEvent(QEvent(QEvent.Type.LanguageChange))

        self.assertEqual(widget._linear_title_label.text(), "Линейна скорост:")
        self.assertEqual(widget._rotation_title_label.text(), "Скорост на въртене:")


if __name__ == "__main__":
    unittest.main()
