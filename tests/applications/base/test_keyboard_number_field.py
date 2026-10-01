import unittest

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from src.applications.base.keyboard_settings_view import build_with_keyboard_setting_handlers
from pl_gui.settings.settings_view.group_widget import GenericSettingGroup
from pl_gui.settings.settings_view.schema import SettingField, SettingGroup


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

    def test_schema_numeric_fields_use_the_shared_control(self):
        schema = SettingGroup("Numbers", [
            SettingField("count", "Count", "spinbox", default=2, min_val=0, max_val=9),
            SettingField("offset", "Offset", "double_spinbox", default=0.5,
                         min_val=0, max_val=1, decimals=2, suffix=" mm"),
        ])
        group = build_with_keyboard_setting_handlers(lambda: GenericSettingGroup(schema))
        self.assertIsInstance(group._widgets["count"], KeyboardNumberField)
        self.assertIsInstance(group._widgets["offset"], KeyboardNumberField)
        group.set_values({"count": 4, "offset": 0.75})
        self.assertEqual(group.get_values(), {"count": 4, "offset": 0.75})

    def test_special_value_and_bounds_update_touch_controls(self):
        field = KeyboardNumberField()
        field.setRange(0, 2)
        field.setSpecialValueText("auto")
        field.setSuffix(" mm")
        self.assertFalse(field._decrease.isEnabled())
        self.assertTrue(field._unit.isHidden())
        field.setValue(2)
        self.assertFalse(field._increase.isEnabled())
        self.assertTrue(field._decrease.isEnabled())
        self.assertFalse(field._unit.isHidden())

    def test_read_only_disables_touch_stepping(self):
        field = KeyboardNumberField(decimal=True)
        field.setRange(-10.0, 10.0)
        field.setValue(2.0)
        field.setReadOnly(True)
        self.assertFalse(field._decrease.isEnabled())
        self.assertFalse(field._increase.isEnabled())
        field.setReadOnly(False)
        self.assertTrue(field._decrease.isEnabled())
        self.assertTrue(field._increase.isEnabled())


if __name__ == "__main__":
    unittest.main()
