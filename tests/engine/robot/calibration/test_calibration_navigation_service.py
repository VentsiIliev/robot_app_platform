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


if __name__ == "__main__":
    unittest.main()
