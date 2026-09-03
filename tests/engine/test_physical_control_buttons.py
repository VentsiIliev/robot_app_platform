import unittest
from unittest.mock import MagicMock

from src.engine.hardware.physical_control_buttons.modbus.modbus_physical_control_buttons import (
    ModbusPhysicalControlButtons,
)


class TestModbusPhysicalControlButtons(unittest.TestCase):
    def test_set_button_writes_configured_output(self) -> None:
        transport = MagicMock()
        buttons = ModbusPhysicalControlButtons(
            transport,
            inputs={"start": "X0"},
            outputs={"start": "Y0"},
        )

        buttons.set_button("start", True)
        self.assertTrue(buttons.is_healthy())
        buttons.set_button("start", False)

        self.assertEqual(transport.write_register.call_args_list[0].args, (128, 1))
        self.assertEqual(transport.write_register.call_args_list[1].args, (128, 0))

    def test_read_output_states_reads_configured_outputs(self) -> None:
        transport = MagicMock()
        transport.read_register.side_effect = [1, 0]
        buttons = ModbusPhysicalControlButtons(
            transport,
            inputs={"start": "X0"},
            outputs={"start": "Y0", "pause": "Y1"},
        )

        self.assertEqual(buttons.read_output_states(), {"start": True, "pause": False})
        self.assertTrue(buttons.is_healthy())

    def test_failed_operation_updates_cached_health(self) -> None:
        transport = MagicMock()
        transport.read_input.side_effect = OSError("offline")
        buttons = ModbusPhysicalControlButtons(transport, inputs={"start": "X0"})

        with self.assertRaises(OSError):
            buttons.read_states()
        self.assertFalse(buttons.is_healthy())


if __name__ == "__main__":
    unittest.main()
