import unittest
from unittest.mock import MagicMock

from src.applications.robot_settings.service.robot_settings_application_service import RobotSettingsApplicationService
from src.robot_systems.glue.settings_ids import SettingsID


def _make_svc(robot=None, nav=None, tool_key=None, tool_settings=None):
    ss = MagicMock()
    if tool_key and tool_settings is not None:
        ss.get.side_effect = lambda k: tool_settings if k == tool_key else None
    return RobotSettingsApplicationService(
        ss,
        config_key=SettingsID.ROBOT_CONFIG,
        calibration_key=SettingsID.ROBOT_CALIBRATION,
        robot_service=robot,
        tool_settings_key=tool_key,
        navigation_service=nav,
    )


class TestGetCurrentPosition(unittest.TestCase):

    def test_returns_none_when_no_robot(self):
        self.assertIsNone(_make_svc().get_current_position())

    def test_delegates_to_robot(self):
        robot = MagicMock()
        robot.get_current_position.return_value = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        self.assertEqual(_make_svc(robot=robot).get_current_position(), [1.0, 2.0, 3.0, 4.0, 5.0, 6.0])

    def test_returns_none_on_robot_exception(self):
        robot = MagicMock()
        robot.get_current_position.side_effect = RuntimeError("disconnected")
        self.assertIsNone(_make_svc(robot=robot).get_current_position())


class TestGetSlotInfo(unittest.TestCase):

    def test_returns_empty_when_no_tool_settings_key(self):
        self.assertEqual(_make_svc().get_slot_info(), [])

    def test_returns_empty_when_settings_returns_none(self):
        ss = MagicMock()
        ss.get.return_value = None
        svc = RobotSettingsApplicationService(
            ss,
            config_key=SettingsID.ROBOT_CONFIG,
            calibration_key=SettingsID.ROBOT_CALIBRATION,
            tool_settings_key="tool_key",
        )
        self.assertEqual(svc.get_slot_info(), [])

    def test_returns_slot_with_assigned_tool_name(self):
        slot = MagicMock(); slot.id = 10; slot.tool_id = 1
        tool = MagicMock(); tool.id = 1;  tool.name = "Gripper"
        tc   = MagicMock(); tc.slots = [slot]; tc.tools = [tool]
        result = _make_svc(tool_key="k", tool_settings=tc).get_slot_info()
        self.assertEqual(result, [(10, "Gripper")])

    def test_returns_none_tool_name_for_unassigned_slot(self):
        slot = MagicMock(); slot.id = 5; slot.tool_id = None
        tc   = MagicMock(); tc.slots = [slot]; tc.tools = []
        result = _make_svc(tool_key="k", tool_settings=tc).get_slot_info()
        self.assertEqual(result, [(5, None)])

    def test_multiple_slots_mixed_assignment(self):
        s1 = MagicMock(); s1.id = 1; s1.tool_id = 2
        s2 = MagicMock(); s2.id = 2; s2.tool_id = None
        t  = MagicMock(); t.id = 2; t.name = "Drill"
        tc = MagicMock(); tc.slots = [s1, s2]; tc.tools = [t]
        result = _make_svc(tool_key="k", tool_settings=tc).get_slot_info()
        self.assertEqual(result, [(1, "Drill"), (2, None)])

    def test_returns_empty_on_exception(self):
        ss = MagicMock()
        ss.get.side_effect = RuntimeError("boom")
        svc = RobotSettingsApplicationService(
            ss,
            config_key=SettingsID.ROBOT_CONFIG,
            calibration_key=SettingsID.ROBOT_CALIBRATION,
            tool_settings_key="tool_key",
        )
        self.assertEqual(svc.get_slot_info(), [])


class TestMoveToGroup(unittest.TestCase):

    def test_returns_false_without_navigation(self):
        self.assertFalse(_make_svc().move_to_group("HOME"))

    def test_delegates_to_navigation_and_returns_true(self):
        nav = MagicMock(); nav.move_to_group.return_value = True
        self.assertTrue(_make_svc(nav=nav).move_to_group("HOME"))
        nav.move_to_group.assert_called_once_with("HOME")

    def test_delegates_to_navigation_and_returns_false(self):
        nav = MagicMock(); nav.move_to_group.return_value = False
        self.assertFalse(_make_svc(nav=nav).move_to_group("HOME"))

    def test_returns_false_on_exception(self):
        nav = MagicMock(); nav.move_to_group.side_effect = RuntimeError("fail")
        self.assertFalse(_make_svc(nav=nav).move_to_group("HOME"))


class TestExecuteGroup(unittest.TestCase):

    def test_returns_false_without_navigation(self):
        self.assertFalse(_make_svc().execute_group("TRAJ"))

    def test_calls_move_linear_group_on_navigation(self):
        nav = MagicMock(); nav.move_linear_group.return_value = True
        self.assertTrue(_make_svc(nav=nav).execute_group("TRAJ"))
        nav.move_linear_group.assert_called_once_with("TRAJ")

    def test_returns_false_on_exception(self):
        nav = MagicMock(); nav.move_linear_group.side_effect = RuntimeError("fail")
        self.assertFalse(_make_svc(nav=nav).execute_group("TRAJ"))


class TestMoveToPoint(unittest.TestCase):

    def test_returns_false_without_navigation(self):
        self.assertFalse(_make_svc().move_to_point("HOME", "[0,0,0,0,0,0]"))

    def test_parses_and_delegates_six_values(self):
        nav = MagicMock(); nav.move_to_position.return_value = True
        result = _make_svc(nav=nav).move_to_point("HOME", "[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]")
        self.assertTrue(result)
        nav.move_to_position.assert_called_once_with([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], "HOME")

    def test_returns_false_for_wrong_arg_count(self):
        nav = MagicMock()
        self.assertFalse(_make_svc(nav=nav).move_to_point("HOME", "[1.0, 2.0, 3.0]"))

    def test_returns_false_for_invalid_format(self):
        nav = MagicMock()
        self.assertFalse(_make_svc(nav=nav).move_to_point("HOME", "not_a_list"))

    def test_returns_false_on_navigation_exception(self):
        nav = MagicMock(); nav.move_to_position.side_effect = RuntimeError("fail")
        self.assertFalse(_make_svc(nav=nav).move_to_point("HOME", "[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]"))


if __name__ == "__main__":
    unittest.main()