import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QDialog

from src.applications.modbus_settings.view.modbus_settings_view import ModbusSettingsView
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


if __name__ == "__main__":
    unittest.main()
