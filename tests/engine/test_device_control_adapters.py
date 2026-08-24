import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.engine.hardware.peripherals import PeripheralBinding, PeripheralConfig
from src.engine.hardware.peripherals.device_control_adapters import (
    DryerDeviceAdapter,
    build_device_control_adapters,
)


class _Binary:
    def __init__(self):
        self.active = False
        self.read_error = None
        self.read_count = 0

    def turn_on(self):
        self.active = True

    def turn_off(self):
        self.active = False

    def read_state(self):
        self.read_count += 1
        if self.read_error is not None:
            raise self.read_error
        return self.active


class _Sensor:
    last_raw_value = 0

    def __init__(self):
        self.healthy = True
        self.read_count = 0

    def is_vacuum_detected(self):
        self.read_count += 1
        return True

    def is_healthy(self):
        return self.healthy


class _Buttons:
    def __init__(self):
        self.outputs = {"start": False}
        self.read_error = None
        self.input_read_count = 0

    def read_output_states(self):
        return dict(self.outputs)

    def read_states(self):
        self.input_read_count += 1
        if self.read_error is not None:
            raise self.read_error
        return {"start": False}

    def set_button(self, name, pressed):
        self.outputs[name] = pressed


class DeviceControlAdaptersTest(unittest.TestCase):
    def setUp(self):
        self.config = PeripheralConfig(
            peripherals={
                "fan": PeripheralBinding(
                    slave_id=1,
                    outputs={"fan": "Y3"},
                    commands={"on": 1, "off": 0},
                ),
                "vacuum_sensor": PeripheralBinding(slave_id=1, inputs={"sensor": "X4"}),
                "physical_control_buttons": PeripheralBinding(
                    slave_id=1,
                    inputs={"start": "X0"},
                    outputs={"start": "Y0"},
                    commands={"start_on": 1, "start_off": 0},
                ),
            }
        )
        self.fan = _Binary()
        self.buttons = _Buttons()

    def test_builds_only_configured_devices_and_exposes_actions(self):
        devices = build_device_control_adapters(
            self.config,
            {
                "fan": self.fan,
                "vacuum_sensor": _Sensor(),
                "physical_control_buttons": self.buttons,
            },
        )

        self.assertEqual(
            [device.key for device in devices],
            ["fan", "vacuum_sensor", "physical_control_buttons"],
        )
        fan = devices[0]
        self.assertTrue(fan.execute("on"))
        self.assertTrue(self.fan.active)
        self.assertEqual(fan.read_state()["active"], True)
        self.assertIsNone(fan.read_state()["healthy"])

        buttons = devices[2]
        self.assertIn("start_on", buttons.actions())
        self.assertTrue(buttons.execute("start_on"))
        self.assertTrue(self.buttons.outputs["start"])
        self.assertIsNone(buttons.read_state()["healthy"])

    def test_missing_service_is_skipped(self):
        devices = build_device_control_adapters(self.config, {})
        self.assertEqual(devices, [])

    def test_device_lifecycle_persists_and_gates_actions(self):
        persisted = []
        fan = build_device_control_adapters(
            self.config,
            {"fan": self.fan},
            lambda key, enabled: persisted.append((key, enabled)),
        )[0]

        self.assertTrue(fan.set_enabled(False))
        self.assertFalse(fan.is_enabled())
        self.assertFalse(fan.execute("on"))
        self.assertEqual(persisted, [("fan", False)])

        self.assertTrue(fan.set_enabled(True))
        self.assertEqual(self.fan.read_count, 1)
        self.assertTrue(fan.execute("on"))
        self.assertTrue(self.fan.active)

    def test_dryer_named_action_uses_named_controller_method(self):
        dryer = MagicMock()
        dryer.is_enabled.return_value = True
        dryer.next_position.return_value = True
        dryer.get_state.side_effect = [
            SimpleNamespace(is_healthy=True, next_position_done=True),
            SimpleNamespace(is_healthy=True, next_position_moving=True, next_position_done=False),
            SimpleNamespace(is_healthy=True, next_position_moving=False, next_position_done=True),
        ]
        adapter = DryerDeviceAdapter(dryer, commands={"next_position": 0})

        self.assertTrue(adapter.execute("next_position"))

        dryer.next_position.assert_called_once_with()
        dryer.execute_command.assert_not_called()

    def test_dryer_next_position_fails_when_no_fresh_status_cycle_is_seen(self):
        dryer = MagicMock()
        dryer.is_enabled.return_value = True
        dryer.next_position.return_value = True
        dryer.get_state.return_value = SimpleNamespace(
            is_healthy=True,
            next_position_moving=False,
            next_position_done=True,
        )
        adapter = DryerDeviceAdapter(dryer, commands={"next_position": 1})

        with patch(
            "src.engine.hardware.peripherals.device_control_adapters.time.monotonic",
            side_effect=[0.0, 10.0],
        ):
            self.assertFalse(adapter.execute("next_position"))

    def test_failed_register_read_keeps_binary_device_disabled(self):
        persisted = []
        self.fan.read_error = OSError("fan offline")
        fan = build_device_control_adapters(
            self.config,
            {"fan": self.fan},
            lambda key, enabled: persisted.append((key, enabled)),
        )[0]

        self.assertFalse(fan.set_enabled(True))
        self.assertFalse(fan.is_enabled())
        self.assertEqual(fan.last_error(), "fan offline")
        self.assertEqual(persisted, [("fan", False)])

    def test_sensor_and_buttons_read_hardware_before_enabling(self):
        sensor = _Sensor()
        devices = build_device_control_adapters(
            self.config,
            {"vacuum_sensor": sensor, "physical_control_buttons": self.buttons},
        )

        sensor_adapter, buttons_adapter = devices
        self.assertTrue(sensor_adapter.set_enabled(True))
        self.assertTrue(buttons_adapter.set_enabled(True))
        self.assertEqual(sensor.read_count, 1)
        self.assertEqual(self.buttons.input_read_count, 1)

        sensor.healthy = False
        self.buttons.read_error = OSError("buttons offline")
        self.assertFalse(sensor_adapter.set_enabled(True))
        self.assertFalse(buttons_adapter.set_enabled(True))
        self.assertFalse(sensor_adapter.is_enabled())
        self.assertFalse(buttons_adapter.is_enabled())

    def test_empty_commands_expose_no_ui_actions(self):
        config = PeripheralConfig({
            "fan": PeripheralBinding(slave_id=1, outputs={"fan": "Y3"}),
            "physical_control_buttons": PeripheralBinding(
                slave_id=1,
                inputs={"start": "X0"},
                outputs={"start": "Y0"},
            ),
        })
        fan, buttons = build_device_control_adapters(
            config,
            {"fan": self.fan, "physical_control_buttons": self.buttons},
        )

        self.assertEqual(fan.actions(), {})
        self.assertEqual(buttons.actions(), {})
        self.assertFalse(fan.execute("on"))
        self.assertFalse(buttons.execute("start_on"))


if __name__ == "__main__":
    unittest.main()
