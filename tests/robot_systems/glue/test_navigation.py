import unittest
from unittest.mock import MagicMock

from src.robot_systems.glue.navigation import GlueNavigationService


class TestGlueNavigationService(unittest.TestCase):

    def test_move_home_goes_directly_to_home(self):
        navigation = MagicMock()
        navigation.move_to_group.return_value = True

        service = GlueNavigationService(navigation=navigation)

        ok = service.move_home()

        self.assertTrue(ok)
        navigation.move_to_group.assert_called_once_with("HOME", wait_cancelled=None)

    def test_move_home_uses_capture_z_offset_when_vision_is_present(self):
        navigation = MagicMock()
        navigation._get_config.return_value = object()
        home_group = MagicMock()
        home_group.parse_position.return_value = [0.0, 0.0, 10.0, 0.0, 0.0, 0.0]
        navigation._get_group.return_value = home_group
        navigation.move_to_position.return_value = True
        vision = MagicMock()
        vision.get_capture_pos_offset.return_value = 5.0

        service = GlueNavigationService(navigation=navigation, vision=vision)

        ok = service.move_home()

        self.assertTrue(ok)
        navigation.move_to_position.assert_called_once_with(
            [0.0, 0.0, 15.0, 0.0, 0.0, 0.0],
            "HOME",
            wait_cancelled=None,
        )

    def test_get_group_position_returns_parsed_position(self):
        navigation = MagicMock()
        navigation._get_config.return_value = object()
        group = MagicMock()
        group.parse_position.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        navigation._get_group.return_value = group

        service = GlueNavigationService(navigation=navigation)

        self.assertEqual(service.get_group_position("HOME"), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
