import unittest
from unittest.mock import MagicMock

from src.engine.robot.calibration.calibration_navigation_service import (
    CalibrationNavigationService,
)


class TestCalibrationNavigationService(unittest.TestCase):
    def test_move_to_calibration_position_runs_before_move_then_navigation(self):
        navigation = MagicMock()
        before_move = MagicMock()
        service = CalibrationNavigationService(
            navigation,
            before_move=before_move,
        )

        service.move_to_calibration_position(wait_cancelled="token")

        before_move.assert_called_once_with()
        navigation.move_to_group.assert_called_once_with(
            "CALIBRATION",
            wait_cancelled="token",
        )

    def test_move_to_calibration_position_propagates_before_move_errors(self):
        navigation = MagicMock()
        service = CalibrationNavigationService(
            navigation,
            before_move=MagicMock(side_effect=KeyError("bad area")),
        )

        with self.assertRaises(KeyError):
            service.move_to_calibration_position()

        navigation.move_to_group.assert_not_called()

    def test_dynamic_group_is_resolved_once_before_move_side_effects(self):
        calls = []
        navigation = MagicMock()
        service = CalibrationNavigationService(
            navigation,
            calibration_group_getter=lambda: calls.append("select") or "Magazine",
            before_move=lambda: calls.append("activate"),
            after_move=lambda: calls.append("verify"),
        )

        service.move_to_calibration_position()

        self.assertEqual(calls, ["select", "activate", "verify"])
        navigation.move_to_group.assert_called_once_with("Magazine", wait_cancelled=None)


if __name__ == "__main__":
    unittest.main()
