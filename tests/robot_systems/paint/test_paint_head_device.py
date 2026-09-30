import unittest
from unittest.mock import MagicMock

from src.robot_systems.paint.hardware.paint_head_device import PaintHeadDevice


class PaintHeadDeviceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.transport = MagicMock()
        self.device = PaintHeadDevice(
            self.transport, 2, min_value=45, max_value=235,
            preset_spacing=38, preset_count=6,
            degree_units_numerator=94, degree_units_denominator=90,
        )

    def test_all_six_presets_match_script_formula(self) -> None:
        for setting, value in enumerate((235, 197, 159, 121, 83, 45), start=1):
            self.transport.read_register.return_value = value
            self.assertEqual(self.device.go_to_setting(setting), value)
            self.transport.write_register.assert_called_with(2, value)

    def test_one_degree_moves_one_register_unit_in_each_direction(self) -> None:
        self.transport.read_register.side_effect = [121, 122, 122, 121]
        self.assertEqual(self.device.move_degrees(1), 122)
        self.assertEqual(self.device.move_degrees(-1), 121)
        self.assertEqual(
            [call.args for call in self.transport.write_register.call_args_list],
            [(2, 122), (2, 121)],
        )

    def test_degree_conversion_matches_script_rounding(self) -> None:
        self.transport.read_register.side_effect = [121, 142]
        self.assertEqual(self.device.move_degrees(20), 142)
        self.transport.write_register.assert_called_once_with(2, 142)

    def test_rejects_out_of_range_target_without_write(self) -> None:
        self.transport.read_register.return_value = 235
        with self.assertRaises(ValueError):
            self.device.move_degrees(1)
        self.transport.write_register.assert_not_called()

    def test_rejects_out_of_range_current_position_without_write(self) -> None:
        self.transport.read_register.return_value = 240
        with self.assertRaises(ValueError):
            self.device.move_degrees(-1)
        self.transport.write_register.assert_not_called()

    def test_allows_in_range_current_position_between_calibrated_steps(self) -> None:
        self.transport.read_register.side_effect = [100, 101]
        self.assertEqual(self.device.move_degrees(1), 101)
        self.transport.write_register.assert_called_once_with(2, 101)

    def test_rejects_non_integer_step_without_read(self) -> None:
        for invalid in (0, True, 1.5):
            with self.assertRaises(ValueError):
                self.device.move_degrees(invalid)
        self.transport.read_register.assert_not_called()

    def test_rejects_invalid_setting_without_write(self) -> None:
        for invalid in (0, 7, 1.5, True):
            with self.assertRaises(ValueError):
                self.device.go_to_setting(invalid)
        self.transport.write_register.assert_not_called()

    def test_reports_readback_mismatch(self) -> None:
        self.transport.read_register.side_effect = [121, 121]
        with self.assertRaises(RuntimeError):
            self.device.move_degrees(1)


if __name__ == "__main__":
    unittest.main()
