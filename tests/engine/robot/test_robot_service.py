import unittest
from unittest.mock import MagicMock

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.services.robot_service import RobotService


class TestRobotService(unittest.TestCase):

    def setUp(self):
        self.motion = MagicMock()
        self.robot  = MagicMock()
        self.state  = MagicMock()
        self.state.velocity     = 25.0
        self.state.acceleration = 15.0
        self.state.state        = "idle"
        self.state.state_topic  = "robot/state"
        self.service = RobotService(self.motion, self.robot, self.state)

    # --- motion delegation ---

    def test_move_ptp_delegates_to_motion(self):
        self.motion.move_ptp.return_value = True
        result = self.service.move_ptp([1, 2, 3, 0, 0, 0], 0, 0, 30, 30)
        self.motion.move_ptp.assert_called_once_with([1, 2, 3, 0, 0, 0], 0, 0, 30, 30, False)
        self.assertTrue(result)

    def test_move_linear_delegates_to_motion(self):
        self.motion.move_linear.return_value = True
        result = self.service.move_linear([1, 2, 3, 0, 0, 0], 0, 0, 20, 20)
        self.motion.move_linear.assert_called_once()
        self.assertTrue(result)

    def test_start_jog_delegates_to_motion(self):
        self.motion.start_jog.return_value = 0
        self.service.start_jog(RobotAxis.Z, Direction.PLUS, 5.0)
        self.motion.start_jog.assert_called_once_with(RobotAxis.Z, Direction.PLUS, 5.0)

    def test_stop_motion_delegates_to_motion(self):
        self.motion.stop_motion.return_value = True
        self.assertTrue(self.service.stop_motion())

    def test_get_current_position_delegates_to_motion(self):
        self.motion.get_current_position.return_value = [1, 2, 3, 0, 0, 0]
        self.assertEqual(self.service.get_current_position(), [1, 2, 3, 0, 0, 0])

    # --- lifecycle delegation ---

    def test_enable_robot_delegates_to_robot(self):
        self.service.enable_robot()
        self.robot.enable.assert_called_once()

    def test_disable_robot_delegates_to_robot(self):
        self.service.disable_robot()
        self.robot.disable.assert_called_once()

    # --- state delegation ---

    def test_get_current_velocity_from_state(self):
        self.assertEqual(self.service.get_current_velocity(), 25.0)

    def test_get_current_acceleration_from_state(self):
        self.assertEqual(self.service.get_current_acceleration(), 15.0)

    def test_get_state_from_state(self):
        self.assertEqual(self.service.get_state(), "idle")

    def test_get_state_topic_from_state(self):
        self.assertEqual(self.service.get_state_topic(), "robot/state")

    # --- tool service ---

    def test_tools_none_by_default(self):
        self.assertIsNone(self.service.tools)

    def test_tools_returns_injected_service(self):
        tool_service = MagicMock()
        svc = RobotService(self.motion, self.robot, self.state, tool_service=tool_service)
        self.assertIs(svc.tools, tool_service)