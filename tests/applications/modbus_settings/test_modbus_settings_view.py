import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from src.applications.base.widgets.custom_virtual_keyboard import KeyboardLineEdit
from src.applications.base.widgets.keyboard_number_field import KeyboardNumberField
from src.applications.modbus_settings.view.modbus_settings_view import (
    ModbusSettingsView, _ModbusProfileDialog, _ModbusSlaveDialog,
)
from src.engine.hardware.communication.modbus.modbus import ModbusConfig, ModbusSlaveConfig


class TestModbusSettingsViewSlaveSelection(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._view = ModbusSettingsView()
        self._view.load_config(ModbusConfig(
            slaves={
                "xinje_ma": ModbusSlaveConfig(
                    slave_address=1,
                    profile_name="default",
                    transport_type="modbus_register",
                    max_retries=12,
                ),
            },
        ))

    def tearDown(self):
        self._view.close()
        self._view.deleteLater()

    def test_selecting_slave_loads_its_values_before_save_capture(self):
        self._view._slave_table.selectRow(1)

        values = self._view.get_slave_values()

        self.assertEqual(values["xinje_ma"]["slave_address"], 1)
        self.assertEqual(values["xinje_ma"]["max_retries"], 12)

    def test_editing_transport_is_not_overwritten_when_selector_is_rebuilt(self):
        self._view._slave_table.selectRow(1)
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.get_values.return_value = (
            "xinje_ma",
            {
                "slave_address": 1,
                "profile_name": "default",
                "transport_type": "xinje_ma_8x8yr",
                "max_retries": 12,
            },
        )

        with patch(
            "src.applications.modbus_settings.view.modbus_settings_view._ModbusSlaveDialog",
            return_value=dialog,
        ):
            self._view._on_edit_slave()

        values = self._view.get_slave_values()
        self.assertEqual(values["xinje_ma"]["transport_type"], "xinje_ma_8x8yr")

    def test_tabs_and_dialog_fields_use_shared_touch_controls(self):
        self.assertEqual(self._view._phase_bar.count(), 2)
        self._view._phase_bar.setCurrentIndex(1)
        self.assertEqual(self._view._tabs.currentIndex(), 1)

        profile = _ModbusProfileDialog({"timeout": 0.5}, name="default")
        slave = _ModbusSlaveDialog({"slave_address": 10, "max_retries": 30}, name="default")
        self.assertIsInstance(profile._name, KeyboardLineEdit)
        self.assertIsInstance(profile._port, KeyboardLineEdit)
        self.assertIsInstance(profile._timeout, KeyboardNumberField)
        self.assertIsInstance(slave._address, KeyboardNumberField)
        self.assertIsInstance(slave._retries, KeyboardNumberField)
        profile._timeout._increase.click()
        slave._address._increase.click()
        self.assertAlmostEqual(profile.get_values()[1]["timeout"], 0.501)
        self.assertEqual(slave.get_values()[1]["slave_address"], 11)

    def test_port_change_can_be_discarded_or_saved(self):
        self.assertFalse(self._view._save_btn.isEnabled())
        self._view._port_combo.addItem("/dev/ttyUSB1")
        self._view._port_combo.setCurrentText("/dev/ttyUSB1")
        self.assertTrue(self._view._save_btn.isEnabled())
        self._view._discard_btn.click()
        self.assertEqual(self._view._port_combo.currentText(), "COM5")
        self.assertFalse(self._view._save_btn.isEnabled())

        self._view._port_combo.addItem("/dev/ttyUSB1")
        self._view._port_combo.setCurrentText("/dev/ttyUSB1")
        self._view.set_save_result(True, "Saved")
        self.assertFalse(self._view._save_btn.isEnabled())
        self.assertEqual(self._view.get_profile_values()["default"]["port"], "/dev/ttyUSB1")

    def test_profile_edit_can_be_discarded(self):
        dialog = MagicMock()
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        changed = dict(self._view.get_profile_values()["default"], baudrate=57600)
        dialog.get_values.return_value = ("default", changed)

        with patch(
            "src.applications.modbus_settings.view.modbus_settings_view._ModbusProfileDialog",
            return_value=dialog,
        ):
            self._view._on_edit_profile()

        self.assertTrue(self._view._save_btn.isEnabled())
        self.assertEqual(int(self._view.get_profile_values()["default"]["baudrate"]), 57600)
        self._view._discard_btn.click()
        self.assertEqual(int(self._view.get_profile_values()["default"]["baudrate"]), 115200)
        self.assertFalse(self._view._save_btn.isEnabled())


if __name__ == "__main__":
    unittest.main()
