import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField


class TestKeyboardNumberField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_tap_steps_once_with_selected_step_and_respects_bounds(self):
        field = KeyboardNumberField(decimal=True)
        field.setRange(0.0, 1.0)
        field.setDecimals(1)
        field.setSingleStep(0.5)
        field.show()

        QTest.mousePress(field._increase, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(field._increase, Qt.MouseButton.LeftButton)
        self.assertEqual(field.value(), 0.5)
        QTest.mousePress(field._increase, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(field._increase, Qt.MouseButton.LeftButton)
        QTest.mousePress(field._increase, Qt.MouseButton.LeftButton)
        QTest.mouseRelease(field._increase, Qt.MouseButton.LeftButton)
        self.assertEqual(field.value(), 1.0)

    def test_hold_accelerates_and_release_stops_repeating(self):
        field = KeyboardNumberField()
        field.setRange(0, 1000)
        field.show()

        QTest.mousePress(field._increase, Qt.MouseButton.LeftButton)
        QTest.qWait(900)
        early = field.value()
        QTest.qWait(900)
        middle = field.value()
        QTest.qWait(900)
        late = field.value()
        QTest.mouseRelease(field._increase, Qt.MouseButton.LeftButton)
        QTest.qWait(200)

        self.assertGreater(early, 1)
        self.assertGreater(late - middle, early)
        self.assertEqual(field.value(), late)

    def test_decrease_hold_uses_selected_step(self):
        field = KeyboardNumberField()
        field.setRange(0, 100)
        field.setSingleStep(10)
        field.setValue(100)
        field.show()

        QTest.mousePress(field._decrease, Qt.MouseButton.LeftButton)
        QTest.qWait(650)
        QTest.mouseRelease(field._decrease, Qt.MouseButton.LeftButton)

        self.assertLessEqual(field.value(), 80)
        self.assertEqual(field.value() % 10, 0)


if __name__ == "__main__":
    unittest.main()
