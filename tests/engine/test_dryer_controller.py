import unittest
from unittest.mock import MagicMock, patch

from src.engine.hardware.dryer.dryer_controller import DryerController
from src.engine.hardware.dryer.models.dryer_config import DryerConfig
from src.engine.hardware.dryer.models.dryer_status import DryerStatus
from src.engine.hardware.dryer.models.dryer_write_data import DryerWriteData
from src.engine.hardware.dryer.models.dryer_modbus_registers import DryerRegisterMap


class TestDryerController(unittest.TestCase):
    def test_robot_system_can_override_commands_and_statuses(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = 0x80
        controller = DryerController(
            transport,
            commands={"eject": 9},
            statuses={"ready": 0x80},
        )

        self.assertTrue(controller.eject())
        self.assertEqual(transport.write_registers.call_args.args[1][1], 9)
        self.assertTrue(controller.get_state().is_ready)

    def test_decodes_current_firmware_status_flags(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = int(
            DryerStatus.READY
            | DryerStatus.EJECT_DONE
            | DryerStatus.NEXT_POS_MOVING
        )
        state = DryerController(transport).get_state()

        self.assertTrue(state.is_ready)
        self.assertTrue(state.eject_done)
        self.assertTrue(state.next_position_moving)

    def test_status_read_logs_raw_register_and_decoded_flags(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = int(
            DryerStatus.READY | DryerStatus.EJECT | DryerStatus.NEXT_POS_DONE
        )
        controller = DryerController(transport)

        with self.assertLogs("DryerController", level="DEBUG") as captured:
            controller.get_state()

        output = "\n".join(captured.output)
        self.assertIn("raw=73 (0x0049)", output)
        self.assertIn("ready=True", output)
        self.assertIn("ejecting=True", output)
        self.assertIn("eject_done=False", output)
        self.assertIn("next_position_done=True", output)

    def test_status_read_retries_using_configured_max_retries(self) -> None:
        transport = MagicMock()
        transport.read_register.side_effect = [
            IOError("no answer"),
            int(DryerStatus.READY | DryerStatus.EJECT_DONE),
        ]
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
        )

        state = controller.get_state()

        self.assertTrue(state.is_healthy)
        self.assertTrue(state.eject_done)
        self.assertEqual(transport.read_register.call_count, 2)

    def test_status_read_reports_unhealthy_after_retries_are_exhausted(self) -> None:
        transport = MagicMock()
        transport.read_register.side_effect = IOError("no answer")
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
        )

        state = controller.get_state()

        self.assertFalse(state.is_healthy)
        self.assertEqual(state.communication_errors, ["no answer"])
        self.assertEqual(transport.read_register.call_count, 3)

    def test_command_replaces_stale_payload_command(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport)

        self.assertTrue(controller.execute_command(0, DryerWriteData(command=2)))

        values = transport.write_registers.call_args.args[1]
        self.assertEqual(values[1], 0)

    def test_execute_command_uses_configured_numeric_value(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport)

        self.assertTrue(controller.execute_command(7))
        values = transport.write_registers.call_args.args[1]
        self.assertEqual(values[1], 7)

    def test_next_position_logs_command_register_target_and_result(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport)

        with self.assertLogs("DryerController", level="INFO") as captured:
            self.assertTrue(controller.next_position())

        output = "\n".join(captured.output)
        self.assertIn("Sending NEXT_POSITION command=0x00 command_register=1", output)
        self.assertIn("NEXT_POSITION FC16 write completed success=True", output)
        transport.write_registers.assert_called_once_with(1, [0])
        transport.write_register.assert_not_called()

    def test_next_position_reports_single_register_write_failure(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = IOError("write failed")
        transport.read_register.return_value = int(DryerStatus.NEXT_POS_DONE)
        controller = DryerController(transport)

        with self.assertLogs("DryerController", level="INFO") as captured:
            self.assertFalse(controller.next_position())

        output = "\n".join(captured.output)
        self.assertIn("NEXT_POSITION FC16 single-register write failed", output)
        self.assertIn("NEXT_POSITION FC16 write completed success=False", output)

    def test_next_position_retries_using_configured_max_retries(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = [IOError("no answer"), None]
        transport.read_register.return_value = int(DryerStatus.NEXT_POS_DONE)
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
            command_settle_s=0.0,
        )

        self.assertTrue(controller.next_position())

        self.assertEqual(transport.write_registers.call_count, 2)
        transport.read_register.assert_called_once_with(0)

    def test_next_position_stops_after_configured_retries_are_exhausted(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = IOError("no answer")
        transport.read_register.return_value = int(DryerStatus.NEXT_POS_DONE)
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
            command_settle_s=0.0,
        )

        self.assertFalse(controller.next_position())

        self.assertEqual(transport.write_registers.call_count, 3)
        self.assertEqual(transport.read_register.call_count, 3)

    def test_next_position_does_not_retry_when_movement_confirms_lost_ack(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = IOError("ack lost")
        transport.read_register.return_value = int(DryerStatus.NEXT_POS_MOVING)
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
            command_settle_s=0.0,
        )

        self.assertTrue(controller.next_position())

        transport.write_registers.assert_called_once_with(1, [0])
        transport.read_register.assert_called_once_with(0)

    def test_initialize_writes_config_then_sends_next_position(self) -> None:
        transport = MagicMock()
        controller = DryerController(
            transport,
            DryerConfig(pwm_open_vrytka=777),
            commands={"next_position": 1},
        )
        transport.read_register.side_effect = [
            int(DryerStatus.NEXT_POS_MOVING),
            int(DryerStatus.NEXT_POS_DONE),
        ]

        self.assertTrue(controller.initialize())

        self.assertEqual(transport.write_registers.call_count, 2)
        address, values = transport.write_registers.call_args_list[0].args
        self.assertEqual(address, 0)
        self.assertEqual(values[1], 0)
        self.assertEqual(values[2], 777)
        self.assertEqual(transport.write_registers.call_args_list[1].args, (1, [1]))
        self.assertEqual(transport.read_register.call_count, 2)

    def test_initialize_does_not_send_next_position_when_config_write_fails(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = IOError("config write failed")
        controller = DryerController(transport, commands={"next_position": 1})

        self.assertFalse(controller.initialize())

        transport.write_registers.assert_called_once()

    def test_initialize_fails_when_next_position_done_is_not_confirmed(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = int(DryerStatus.NEXT_POS_DONE)
        controller = DryerController(
            transport,
            commands={"next_position": 1},
            next_position_timeout_s=0.0,
            status_poll_interval_s=0.0,
            command_settle_s=0.0,
        )

        self.assertFalse(controller.initialize())

        self.assertEqual(transport.write_registers.call_args_list[-1].args, (1, [1]))
        transport.read_register.assert_called_once_with(0)

    def test_decodes_every_firmware_status_flag(self) -> None:
        transport = MagicMock()
        transport.read_register.return_value = sum(int(status) for status in DryerStatus)

        state = DryerController(transport).get_state()

        self.assertTrue(state.is_ready)
        self.assertTrue(state.ejecting)
        self.assertTrue(state.eject_done)
        self.assertTrue(state.next_position_moving)
        self.assertTrue(state.next_position_done)

    def test_writes_current_seventeen_register_block(self) -> None:
        transport = MagicMock()
        config = DryerConfig()
        controller = DryerController(transport, config)

        self.assertTrue(controller.write_data(DryerWriteData()))

        address, values = transport.write_registers.call_args.args
        self.assertEqual(address, 0)
        self.assertEqual(len(values), 17)
        self.assertEqual(values[2:6], [
            config.pwm_open_vrytka,
            config.pwm_close_vrytka,
            config.pwm_open_izbutvatel,
            config.pwm_close_izbutvatel,
        ])
        self.assertEqual(values[13], 50)
        self.assertEqual(values[14], 1)

    def test_write_data_retries_using_configured_max_retries(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = [IOError("no answer"), None]
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
        )

        self.assertTrue(controller.write_data(DryerWriteData()))

        self.assertEqual(transport.write_registers.call_count, 2)

    def test_write_data_stops_after_configured_retries_are_exhausted(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = IOError("no answer")
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
        )

        self.assertFalse(controller.write_data(DryerWriteData()))

        self.assertEqual(transport.write_registers.call_count, 3)

    def test_rev_minute_is_transmitted_without_scaling(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport, DryerConfig(rev_minute=7))
        transport.read_register.side_effect = [
            int(DryerStatus.NEXT_POS_MOVING),
            int(DryerStatus.NEXT_POS_DONE),
        ]

        self.assertTrue(controller.initialize())

        values = transport.write_registers.call_args_list[0].args[1]
        self.assertEqual(values[13], 7)

    def test_successful_commands_wait_before_status_can_be_checked(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport, command_settle_s=0.03)

        with patch("src.engine.hardware.dryer.dryer_controller.time.sleep") as sleep:
            self.assertTrue(controller.eject())

        sleep.assert_called_once_with(0.03)

    def test_eject_retries_using_configured_max_retries(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = [IOError("no answer"), None]
        transport.read_register.return_value = int(DryerStatus.READY)
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
            command_settle_s=0.0,
        )

        self.assertTrue(controller.eject())

        self.assertEqual(transport.write_registers.call_count, 2)
        transport.read_register.assert_called_once_with(0)

    def test_eject_does_not_retry_when_status_confirms_lost_ack(self) -> None:
        transport = MagicMock()
        transport.write_registers.side_effect = IOError("ack lost")
        transport.read_register.return_value = int(DryerStatus.EJECT)
        controller = DryerController(
            transport,
            max_retries=2,
            status_poll_interval_s=0.0,
            command_settle_s=0.0,
        )

        self.assertTrue(controller.eject())

        self.assertEqual(transport.write_registers.call_count, 1)
        transport.read_register.assert_called_once_with(0)

    def test_acceleration_is_transmitted_in_integer_tenths(self) -> None:
        transport = MagicMock()
        controller = DryerController(transport, DryerConfig())

        self.assertTrue(controller.write_data(DryerWriteData(acceleration=1.7)))

        values = transport.write_registers.call_args.args[1]
        self.assertEqual(values[14], 17)

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
