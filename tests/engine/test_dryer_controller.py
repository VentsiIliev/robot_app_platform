import unittest
from unittest.mock import MagicMock

from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData
from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerRegisterMap


class TestDryerController(unittest.TestCase):
    def test_execute_command_uses_configured_numeric_value(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport)

        self.assertTrue(controller.execute_command(7))
        values = transport.write_registers.call_args.args[1]
        self.assertEqual(values[1], 7)

    def test_initialize_writes_current_config_with_neutral_command(self) -> None:
        transport = MagicMock()
        controller = DryerController(
            transport,
            DryerConfig(pwm_open_vrytka=777),
        )

        self.assertTrue(controller.initialize())

        address, values = transport.write_registers.call_args.args
        self.assertEqual(address, 0)
        self.assertEqual(values[1], 0)
        self.assertEqual(values[2], 777)

    def test_writes_current_eighteen_register_block(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport, DryerConfig())

        self.assertTrue(controller.write_data(DryerWriteData()))

        address, values = transport.write_registers.call_args.args
        self.assertEqual(address, 0)
        self.assertEqual(len(values), 18)
        self.assertEqual(values[2:6], [600, 150, 600, 180])
        self.assertEqual(values[14], 1)

    def test_updated_config_is_used_by_subsequent_default_commands(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport, DryerConfig())
        controller.update_config(DryerConfig(pwm_open_vrytka=777))

        self.assertTrue(controller.move_servos())

        values = transport.write_registers.call_args.args[1]
        self.assertEqual(values[2], 777)

    def test_robot_system_can_override_register_addresses(self) -> None:
        transport = MagicMock()
        addresses = {
            name: address + 100
            for name, address in zip(
                DryerRegisterMap.__dataclass_fields__,
                DryerRegisterMap().addresses,
            )
        }
        controller = DryerController(
            transport,
            DryerConfig(),
            DryerRegisterMap.from_mapping(addresses),
        )

        controller.write_data(DryerWriteData())
        transport.write_registers.assert_called_once()
        self.assertEqual(transport.write_registers.call_args.args[0], 100)


if __name__ == "__main__":
    unittest.main()
