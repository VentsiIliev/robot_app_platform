import unittest
from unittest.mock import MagicMock

from src.engine.hardware.dryer.modbus.modbus_plate_dryer_controller import (
    ModbusPlateDryerController,
)


class TestModbusPlateDryerController(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = MagicMock()
        self.controller = ModbusPlateDryerController(
            transport=self.transport,
            plate_register=2,
            open_value=2,
            close_value=0,
        )

    def test_open_plate_writes_register_two(self) -> None:
        self.assertTrue(self.controller.open_plate())
        self.transport.write_registers.assert_called_once_with(2, [2])

    def test_close_plate_writes_register_two(self) -> None:
        self.assertTrue(self.controller.close_plate())
        self.transport.write_registers.assert_called_once_with(2, [0])

    def test_other_operations_are_no_ops(self) -> None:
        self.assertTrue(self.controller.move_servos())
        self.assertTrue(self.controller.next_position())
        self.assertTrue(self.controller.write_data(MagicMock()))
        self.assertFalse(self.controller.get_state().is_healthy)
        self.transport.write_register.assert_not_called()


if __name__ == "__main__":
    unittest.main()
