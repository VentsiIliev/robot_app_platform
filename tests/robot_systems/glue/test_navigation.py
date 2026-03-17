import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.navigation import GlueNavigationService


class TestGlueNavigationService(unittest.TestCase):

    def test_move_home_routes_via_calibration_when_robot_is_away_from_home_and_calibration(self):
        navigation = MagicMock()
        navigation._get_config.return_value = object()
        home_group = MagicMock()
        home_group.parse_position.return_value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        calibration_group = MagicMock()
        calibration_group.parse_position.return_value = [100.0, 100.0, 100.0, 0.0, 0.0, 0.0]
        navigation._get_group.side_effect = lambda _cfg, name: {
            "HOME": home_group,
            "CALIBRATION": calibration_group,
        }[name]
        navigation.move_to_group.return_value = True
        robot = MagicMock()
        robot.get_current_position.return_value = [500.0, 500.0, 500.0, 0.0, 0.0, 0.0]

        service = GlueNavigationService(navigation=navigation, robot_service=robot)

        ok = service.move_home()

        self.assertTrue(ok)
        self.assertEqual(navigation.move_to_group.call_count, 2)
        first_call = navigation.move_to_group.call_args_list[0]
        second_call = navigation.move_to_group.call_args_list[1]
        self.assertEqual(first_call.args[0], "CALIBRATION")
        self.assertEqual(second_call.args[0], "HOME")

    def test_move_home_skips_calibration_when_already_near_home(self):
        navigation = MagicMock()
        navigation._get_config.return_value = object()
        home_group = MagicMock()
        home_group.parse_position.return_value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        calibration_group = MagicMock()
        calibration_group.parse_position.return_value = [100.0, 100.0, 100.0, 0.0, 0.0, 0.0]
        navigation._get_group.side_effect = lambda _cfg, name: {
            "HOME": home_group,
            "CALIBRATION": calibration_group,
        }[name]
        navigation.move_to_group.return_value = True
        robot = MagicMock()
        robot.get_current_position.return_value = [5.0, 5.0, 5.0, 0.0, 0.0, 0.0]

        service = GlueNavigationService(navigation=navigation, robot_service=robot)

        ok = service.move_home()

        self.assertTrue(ok)
        navigation.move_to_position.assert_not_called()
        navigation.move_to_group.assert_called_once_with("HOME")
