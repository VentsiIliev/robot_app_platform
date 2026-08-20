import unittest

from src.engine.hardware.peripherals import PeripheralBinding, PeripheralConfig
from src.engine.hardware.peripherals.device_control_adapters import (
    build_device_control_adapters,
)


class _Binary:
    def __init__(self):
        self.active = False

    def turn_on(self):
        self.active = True

    def turn_off(self):
        self.active = False


class _Sensor:
    last_raw_value = 0

    def is_vacuum_detected(self):
        return True

    def is_healthy(self):
        return True


class _Buttons:
    def __init__(self):
        self.outputs = {"start": False}

    def read_output_states(self):
        return dict(self.outputs)

    def read_states(self):
        return {"start": False}

    def set_button(self, name, pressed):
        self.outputs[name] = pressed


class DeviceControlAdaptersTest(unittest.TestCase):
    def setUp(self):
        self.config = PeripheralConfig(
            peripherals={
                "fan": PeripheralBinding(slave_id=1, outputs={"fan": "Y3"}),
                "vacuum_sensor": PeripheralBinding(slave_id=1, inputs={"sensor": "X4"}),
                "physical_control_buttons": PeripheralBinding(
                    slave_id=1,
                    inputs={"start": "X0"},
                    outputs={"start": "Y0"},
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

        buttons = devices[2]
        self.assertIn("output:start:on", buttons.actions())
        self.assertTrue(buttons.execute("output:start:on"))
        self.assertTrue(self.buttons.outputs["start"])

    def test_missing_service_is_skipped(self):
        devices = build_device_control_adapters(self.config, {})
        self.assertEqual(devices, [])


if __name__ == "__main__":
    unittest.main()
