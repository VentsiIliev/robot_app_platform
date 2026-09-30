from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.hardware.communication.modbus.modbus import ModbusConfig
from src.engine.hardware.peripherals import PeripheralConfig
from src.robot_systems.paint.applications.paint_adjustment.service.paint_adjustment_service import (
    PaintAdjustmentService,
)
from src.robot_systems.paint.applications.paint_head_settings.paint_head_settings_service import (
    PaintHeadSettingsService,
)
from src.robot_systems.paint.applications.paint_head_settings.paint_head_settings_view import (
    PaintHeadSettingsView,
)
from src.robot_systems.paint.component_ids import SettingsID


class PaintHeadSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.modbus = ModbusConfig.from_dict({
            "port": "/dev/test",
            "slave_address": 10,
            "slaves": {"default": {
                "slave_address": 10,
                "profile_name": "default",
                "transport_type": "modbus_register_fc16",
            }},
        })
        self.current = PeripheralConfig.from_dict({
            "paint_head": {
                "enabled": False,
                "slave_id": 10,
                "outputs": {"position": "2"},
                "commands": {
                    "min_value": 45,
                    "max_value": 235,
                    "preset_spacing": 38,
                    "preset_count": 6,
                    "degree_units_numerator": 94,
                    "degree_units_denominator": 90,
                    "more_paint_sign": -1,
                },
            }
        })
        self.settings = MagicMock()
        self.settings.get.side_effect = self._get
        self.settings.save.side_effect = self._save
        self.service = PaintHeadSettingsService(self.settings)

    def _get(self, key):
        if key == SettingsID.PERIPHERALS:
            return self.current
        if key == CommonSettingsID.MODBUS_CONFIG:
            return self.modbus
        self.fail(f"Unexpected settings key: {key}")

    def _save(self, key, value):
        self.assertEqual(key, SettingsID.PERIPHERALS)
        self.current = value

    def test_saves_direction_spacing_and_count_without_losing_binding(self):
        self.assertEqual(self.service.load().more_paint_sign, -1)
        updated = self.service.save(1, 20, 8)
        binding = self.current.peripherals["paint_head"]
        self.assertEqual((updated.preset_spacing, updated.preset_count), (20, 8))
        self.assertEqual(binding.commands["max_value"], 185)
        self.assertEqual(binding.commands["more_paint_sign"], 1)
        self.assertFalse(binding.enabled)
        self.assertEqual(binding.outputs["position"], "2")
        self.assertEqual(self.service.load(), updated)
        self.settings.save.assert_called_once()

    def test_rejects_invalid_calibration_without_saving(self):
        for sign, spacing, count in ((0, 38, 6), (-1, 0, 6), (-1, 38, 25), (-1, 65535, 24)):
            with self.assertRaises(ValueError):
                self.service.save(sign, spacing, count)
        self.settings.save.assert_not_called()

    def test_adjustment_uses_new_calibration_without_rebuild(self):
        registry = MagicMock()
        adjustment = PaintAdjustmentService(self.settings, registry)
        self.assertEqual(adjustment.get_preset_count(), 6)

        self.service.save(1, 20, 8)

        self.assertEqual(adjustment.get_preset_count(), 8)
        self.assertEqual(adjustment.go_to_setting(1).value, 185)
        self.assertEqual(adjustment.go_to_setting(8).value, 45)
        self.assertEqual(adjustment.adjust_paint("more", 1).value, 1)
        registry.build_for_slave.return_value.read_register.assert_not_called()

    def test_view_exposes_saved_values_and_direction(self):
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        view = PaintHeadSettingsView()
        view.set_settings(-1, 38, 6, 45)
        self.assertEqual(view._direction.currentData(), -1)
        self.assertIn("235", view._range.text())
        view._spacing.setValue(20)
        view._count.setValue(8)
        self.assertIn("185", view._range.text())
        signals = []
        def record(sign, spacing, count):
            signals.append((sign, spacing, count))
        view.save_requested.connect(record)
        view._on_save()
        self.assertEqual(signals, [(-1, 20, 8)])


if __name__ == "__main__":
    unittest.main()
