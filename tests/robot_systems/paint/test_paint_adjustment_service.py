import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.peripherals import PeripheralConfig
from src.robot_systems.paint.applications.paint_adjustment.service.paint_adjustment_service import (
    PaintAdjustmentService,
)
from src.robot_systems.paint.component_ids import SettingsID
from src.robot_systems.paint.hardware.paint_head_availability_adapter import (
    PaintHeadAvailabilityAdapter,
)
from src.robot_systems.paint.processes.paint.incremental_adjustment import AdjustmentStep
from src.robot_systems.paint.applications.paint_adjustment.service.i_paint_adjustment_service import PaintAdjustmentOptions


class PaintAdjustmentServiceTests(unittest.TestCase):
    def test_tray_profile_enables_plus_and_minus_direction(self):
        root = Path(__file__).resolve().parents[3]
        hardware = root / "src/robot_systems/paint/profiles/tray_dryer/storage/settings/hardware"
        modbus = ModbusConfig.from_dict(json.loads((hardware / "modbus.json").read_text()))
        peripherals = PeripheralConfig.from_dict(
            json.loads((hardware / "peripherals.json").read_text())
        )
        settings = MagicMock()
        settings.get.side_effect = lambda key: {
            CommonSettingsID.MODBUS_CONFIG: modbus,
            SettingsID.PERIPHERALS: peripherals,
            SettingsID.PAINT_ADJUSTMENT_SETTINGS: AdjustmentStep(10, 30, -20),
        }[key]
        registry = MagicMock()
        transport = registry.build_for_slave.return_value
        service = PaintAdjustmentService(settings, registry)

        self.assertTrue(service.is_paint_head_available())
        transport.read_register.side_effect = [121, 120, 120, 121, 235]
        self.assertEqual(service.adjust_paint("more", 1).value, 120)
        self.assertEqual(service.adjust_paint("less", 1).value, 121)
        self.assertEqual(service.go_to_setting(1).value, 235)
        self.assertEqual(
            [call.args for call in transport.write_register.call_args_list],
            [(2, 120), (2, 121), (2, 235)],
        )

    def _service(self, *, sign=None, enabled=True, transport_type="modbus_register_fc16"):
        modbus = ModbusConfig.from_dict({
            "port": "/dev/test",
            "slave_address": 10,
            "slaves": {
                "default": {
                    "slave_address": 10,
                    "profile_name": "default",
                    "transport_type": transport_type,
                }
            },
        })
        commands = {
            "min_value": 45,
            "max_value": 235,
            "preset_spacing": 38,
            "preset_count": 6,
            "degree_units_numerator": 94,
            "degree_units_denominator": 90,
        }
        if sign is not None:
            commands["more_paint_sign"] = sign
        peripherals = PeripheralConfig.from_dict({
            "paint_head": {
                "enabled": enabled,
                "slave_id": 10,
                "outputs": {"position": "2"},
                "commands": commands,
            }
        })
        settings = MagicMock()
        settings.get.side_effect = lambda key: {
            CommonSettingsID.MODBUS_CONFIG: modbus,
            SettingsID.PERIPHERALS: peripherals,
            SettingsID.PAINT_ADJUSTMENT_SETTINGS: AdjustmentStep(10, 30, -20),
        }[key]
        registry = MagicMock()
        transport = registry.build_for_slave.return_value
        return PaintAdjustmentService(settings, registry), transport

    def test_missing_direction_disables_commands(self):
        service, transport = self._service()
        self.assertFalse(service.is_paint_head_available())
        with self.assertRaises(KeyError):
            service.adjust_paint("more", 1)
        transport.read_register.assert_not_called()

    def test_rejects_wrong_transport(self):
        service, transport = self._service(sign=1, transport_type="xinje_ma_8x8yr")
        self.assertFalse(service.is_paint_head_available())
        with self.assertRaises(ValueError):
            service.adjust_paint("more", 1)
        transport.read_register.assert_not_called()

    def test_adjusts_relative_to_current_register(self):
        service, transport = self._service(sign=1)
        self.assertTrue(service.is_paint_head_available())
        transport.read_register.side_effect = [121, 122, 122, 121]
        self.assertEqual(service.adjust_paint("more", 1).value, 122)
        self.assertEqual(service.adjust_paint("less", 1).value, 121)
        self.assertEqual(
            transport.write_register.call_args_list[0].args, (2, 122)
        )
        self.assertEqual(
            transport.write_register.call_args_list[1].args, (2, 121)
        )

    def test_register_step_uses_units_without_preset_or_degree_conversion(self):
        service, transport = self._service(sign=-1)
        transport.read_register.side_effect = [121, 118, 118, 120]
        self.assertEqual(service.adjust_paint_by_register_units("more", 3).value, 118)
        self.assertEqual(service.adjust_paint_by_register_units("less", 2).value, 120)
        self.assertEqual(
            [call.args for call in transport.write_register.call_args_list],
            [(2, 118), (2, 120)],
        )
        with self.assertRaises(ValueError):
            service.adjust_paint_by_register_units("more", 0)

        disabled, disabled_transport = self._service(sign=-1, enabled=False)
        preview = disabled.adjust_paint_by_register_units("more", 3)
        self.assertEqual((preview.value, preview.wrote, preview.relative), (-3, False, True))
        disabled_transport.read_register.assert_not_called()
        disabled_transport.write_register.assert_not_called()

    def test_register_step_checks_calibrated_range_before_write(self):
        service, transport = self._service(sign=-1)
        transport.read_register.return_value = 45
        with self.assertRaises(ValueError):
            service.adjust_paint_by_register_units("more", 1)
        transport.write_register.assert_not_called()

    def test_disabled_device_logs_calculations_without_hardware_io(self):
        service, transport = self._service(sign=1, enabled=False)
        self.assertTrue(service.is_paint_head_available())
        with self.assertLogs(
            "src.robot_systems.paint.applications.paint_adjustment.service.paint_adjustment_service",
            level="INFO",
        ) as logs:
            relative = service.adjust_paint("less", 1)
            preset = service.go_to_setting(1)
        self.assertEqual((relative.value, relative.wrote, relative.relative), (-1, False, True))
        self.assertEqual((preset.value, preset.wrote, preset.relative), (235, False, False))
        self.assertIn("delta -1", logs.output[0])
        self.assertIn("absolute value 235", logs.output[1])
        transport.read_register.assert_not_called()
        transport.write_register.assert_not_called()

    def test_dial_configuration_and_position_read(self):
        service, transport = self._service(sign=-1)
        config = service.get_dial_config()
        self.assertEqual((config.minimum, config.spacing, config.count, config.enabled),
                         (45, 38, 6, True))
        transport.read_register.return_value = 121
        self.assertEqual(service.read_current_position(), 121)
        transport.read_register.assert_called_once_with(2)

        disabled, disabled_transport = self._service(sign=-1, enabled=False)
        self.assertIsNone(disabled.read_current_position())
        disabled_transport.read_register.assert_not_called()

    def test_dial_writes_intermediate_position_and_validates_range(self):
        service, transport = self._service(sign=1)
        transport.read_register.return_value = 216
        result = service.go_to_position(216)
        self.assertEqual((result.value, result.wrote, result.relative), (216, True, False))
        transport.write_register.assert_called_once_with(2, 216)
        transport.read_register.assert_called_once_with(2)
        for invalid in (44, 236, True, 216.5):
            with self.assertRaises(ValueError):
                service.go_to_position(invalid)
        transport.write_register.assert_called_once()

        disabled, disabled_transport = self._service(sign=1, enabled=False)
        preview = disabled.go_to_position(216)
        self.assertEqual((preview.value, preview.wrote), (216, False))
        disabled_transport.write_register.assert_not_called()
        disabled_transport.read_register.assert_not_called()

    def test_single_cycle_delegates_without_changing_settings(self):
        service, _transport = self._service(sign=-1)
        start = MagicMock(return_value=True)
        service._start_single_cycle = start
        service._get_cycle_state = MagicMock(return_value="stopped")
        self.assertTrue(service.start_single_paint_cycle())
        self.assertEqual(service.get_paint_cycle_state(), "stopped")
        start.assert_called_once_with()
        service._settings.set.assert_not_called()

    def test_adjustment_options_are_saved_before_start_and_each_next_section(self):
        service, _transport = self._service(sign=-1)
        service._start_adjustment = MagicMock(return_value=True)
        service._paint_next = MagicMock(return_value=True)
        service._finish_adjustment = MagicMock(return_value=True)
        options = PaintAdjustmentOptions(10, 30, -20)
        self.assertEqual(service.get_adjustment_options(), options)
        self.assertTrue(service.start_adjustment_cycle(options))
        self.assertTrue(service.paint_next_section(options))
        self.assertTrue(service.finish_adjustment_cycle())
        service._settings.save.assert_any_call(
            SettingsID.PAINT_ADJUSTMENT_SETTINGS, AdjustmentStep(10, 30, -20)
        )
        service._paint_next.assert_called_once_with(AdjustmentStep(10, 30, -20))
        with self.assertRaises(ValueError):
            service.start_adjustment_cycle(PaintAdjustmentOptions(10, 0, 0))
        self.assertEqual(service._start_adjustment.call_count, 1)

    def test_open_adjustment_service_follows_devices_toggle_immediately(self):
        service, transport = self._service(sign=1)
        settings = service._settings

        def enabled() -> bool:
            return settings.get(SettingsID.PERIPHERALS).peripherals["paint_head"].enabled

        def persist(_key: str, value: bool) -> None:
            config = settings.get(SettingsID.PERIPHERALS)
            config.peripherals["paint_head"] = replace(
                config.peripherals["paint_head"], enabled=value
            )

        adapter = PaintHeadAvailabilityAdapter(enabled, persist)
        self.assertTrue(adapter.set_enabled(False))
        self.assertTrue(service.is_paint_head_available())
        self.assertEqual(service.adjust_paint("less", 1).value, -1)
        transport.read_register.assert_not_called()
        transport.write_register.assert_not_called()

        self.assertTrue(adapter.set_enabled(True))
        transport.read_register.side_effect = [121, 122]
        self.assertEqual(service.adjust_paint("more", 1).value, 122)
        transport.write_register.assert_called_once_with(2, 122)

    def test_step_must_be_positive_integer(self):
        service, transport = self._service(sign=1)
        for step in (0, -1, 1.5, True):
            with self.assertRaises(ValueError):
                service.adjust_paint("more", step)
        transport.read_register.assert_not_called()


if __name__ == "__main__":
    unittest.main()
