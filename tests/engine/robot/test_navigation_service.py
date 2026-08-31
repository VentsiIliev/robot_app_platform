import unittest
from unittest.mock import MagicMock

from src.engine.common_settings_ids import CommonSettingsID
from src.engine.robot.configuration import MovementGroup, MovementGroupSettings, RobotSettings
from src.engine.robot.features.navigation_service import NavigationService


class _Settings:
    def __init__(self, group: MovementGroup):
        self._robot = RobotSettings(robot_tool=2, robot_user=3)
        self._groups = MovementGroupSettings(movement_groups={"HOME": group})

    def get(self, key):
        if key == CommonSettingsID.ROBOT_CONFIG:
            return self._robot
        if key == CommonSettingsID.MOVEMENT_GROUPS:
            return self._groups
        raise KeyError(key)


class TestNavigationService(unittest.TestCase):
    def test_move_to_group_uses_ptp_by_default(self):
        motion = MagicMock()
        motion.move_ptp.return_value = True
        group = MovementGroup(
            velocity=40,
            acceleration=50,
            position="[1, 2, 3, 4, 5, 6]",
        )
        service = NavigationService(
            motion,
            CommonSettingsID.ROBOT_CONFIG,
            CommonSettingsID.MOVEMENT_GROUPS,
            settings_service=_Settings(group),
        )

        self.assertTrue(service.move_to_group("HOME"))

        motion.move_ptp.assert_called_once_with(
            position=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            tool=2,
            user=3,
            velocity=40,
            acceleration=50,
            wait_to_reach=True,
            wait_cancelled=None,
        )
        motion.move_linear.assert_not_called()

    def test_move_to_group_uses_configured_linear_type(self):
        motion = MagicMock()
        motion.move_linear.return_value = True
        group = MovementGroup(
            velocity=41,
            acceleration=51,
            motion_type="linear",
            position="[6, 5, 4, 3, 2, 1]",
        )
        service = NavigationService(
            motion,
            CommonSettingsID.ROBOT_CONFIG,
            CommonSettingsID.MOVEMENT_GROUPS,
            settings_service=_Settings(group),
        )

        self.assertTrue(service.move_to_group("HOME"))

        motion.move_linear.assert_called_once_with(
            position=[6.0, 5.0, 4.0, 3.0, 2.0, 1.0],
            tool=2,
            user=3,
            velocity=41,
            acceleration=51,
            blendR=0.0,
            wait_to_reach=True,
            wait_cancelled=None,
        )
        motion.move_ptp.assert_not_called()

    def test_move_to_position_uses_group_motion_type(self):
        motion = MagicMock()
        motion.move_linear.return_value = True
        group = MovementGroup(velocity=10, acceleration=20, motion_type="linear")
        service = NavigationService(
            motion,
            CommonSettingsID.ROBOT_CONFIG,
            CommonSettingsID.MOVEMENT_GROUPS,
            settings_service=_Settings(group),
        )

        self.assertTrue(service.move_to_position([1, 2, 3, 4, 5, 6], "HOME", velocity=70, acceleration=80))

        motion.move_linear.assert_called_once_with(
            position=[1, 2, 3, 4, 5, 6],
            tool=2,
            user=3,
            velocity=70,
            acceleration=80,
            blendR=0.0,
            wait_to_reach=True,
            wait_cancelled=None,
        )

    def test_move_to_group_allows_motion_type_and_blend_override(self):
        motion = MagicMock()
        motion.move_linear.return_value = True
        group = MovementGroup(
            velocity=10,
            acceleration=20,
            motion_type="ptp",
            position="[1, 2, 3, 4, 5, 6]",
        )
        service = NavigationService(
            motion,
            CommonSettingsID.ROBOT_CONFIG,
            CommonSettingsID.MOVEMENT_GROUPS,
            settings_service=_Settings(group),
        )

        self.assertTrue(service.move_to_group("HOME", motion_type="linear", blendR=8.5))

        motion.move_linear.assert_called_once_with(
            position=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            tool=2,
            user=3,
            velocity=10,
            acceleration=20,
            blendR=8.5,
            wait_to_reach=True,
            wait_cancelled=None,
        )
        motion.move_ptp.assert_not_called()

    def test_move_to_group_allows_fast_lin_override(self):
        motion = MagicMock()
        motion.move_fast_linear.return_value = {
            "result": 0,
            "success": True,
            "accepted": True,
            "final": True,
            "queued": False,
        }
        group = MovementGroup(
            velocity=70,
            acceleration=40,
            motion_type="ptp",
            position="[1, 2, 3, 4, 5, 6]",
        )
        service = NavigationService(
            motion,
            CommonSettingsID.ROBOT_CONFIG,
            CommonSettingsID.MOVEMENT_GROUPS,
            settings_service=_Settings(group),
        )

        self.assertTrue(service.move_to_group("HOME", motion_type="fast_lin"))

        motion.move_fast_linear.assert_called_once_with(
            position=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            tool=2,
            user=3,
            vel=70,
            acc=40,
            trajectory_optimizer="TOTG",
        )
        motion.move_ptp.assert_not_called()
        motion.move_linear.assert_not_called()


class TestMovementGroupMotionType(unittest.TestCase):
    def test_from_dict_defaults_to_ptp_and_serializes_motion_type(self):
        group = MovementGroup.from_dict({"velocity": 10, "acceleration": 20})

        self.assertEqual(group.motion_type, "ptp")
        self.assertEqual(group.to_dict()["motion_type"], "ptp")

    def test_from_dict_preserves_linear_motion_type(self):
        group = MovementGroup.from_dict({"motion_type": "linear"})

        self.assertEqual(group.motion_type, "linear")

    def test_from_dict_preserves_fast_lin_motion_type(self):
        group = MovementGroup.from_dict({"motion_type": "fast_lin"})

        self.assertEqual(group.motion_type, "fast_lin")
        self.assertEqual(group.to_dict()["motion_type"], "fast_lin")


if __name__ == "__main__":
    unittest.main()
