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

    def test_maximum_linear_servo_speed_is_labeled_and_requested_as_200_mm_s(self) -> None:
        widget = RobotJogWidget()
        requests = []
        widget.jog_requested.connect(
            lambda command, axis, direction, value: requests.append(
                (command, axis, direction, value)
            )
        )

        widget._linear_slider.setValue(widget._linear_slider.maximum())
        widget._servo_mode_btn.click()
        widget._perform_jog("x_plus")

        self.assertEqual("200 mm/s", widget._linear_label.text())
        self.assertEqual(("SERVO_JOG", "X", "Plus", 200), requests[-1])

    def test_maximum_linear_step_remains_250_mm(self) -> None:
        widget = RobotJogWidget()
        requests = []
        widget.jog_requested.connect(
            lambda command, axis, direction, value: requests.append(
                (command, axis, direction, value)
            )
        )

        widget._linear_slider.setValue(widget._linear_slider.maximum())
        widget._perform_jog("x_plus")

        self.assertEqual("250 mm", widget._linear_label.text())
        self.assertEqual(("JOG_ROBOT", "X", "Plus", 250), requests[-1])


if __name__ == "__main__":
    unittest.main()
