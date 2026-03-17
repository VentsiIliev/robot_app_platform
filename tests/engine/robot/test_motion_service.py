import unittest
from unittest.mock import MagicMock, patch

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.services.motion_service import MotionService


class TestMotionService(unittest.TestCase):

    def setUp(self):
        self.robot = MagicMock()
        self.safety = MagicMock()
        self.safety.get_violations.return_value = []
        self.service = MotionService(self.robot, self.safety)

    # ------------------------------------------------------------------
    # move_ptp
    # ------------------------------------------------------------------

    def test_move_ptp_success(self):
        self.robot.move_ptp.return_value = 0
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertTrue(result)
        self.robot.move_ptp.assert_called_once()

    def test_move_ptp_uses_non_blocking_robot_call_when_not_waiting(self):
        self.robot.move_ptp.return_value = 0
        self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30, wait_to_reach=False)
        _, kwargs = self.robot.move_ptp.call_args
        self.assertEqual(kwargs.get("blocking"), False)

    def test_move_ptp_accepts_queued_result(self):
        self.robot.move_ptp.return_value = 2
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertTrue(result)

    def test_move_ptp_blocked_by_safety(self):
        self.safety.get_violations.return_value = ["out of bounds"]
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertFalse(result)
        self.robot.move_ptp.assert_not_called()

    def test_move_ptp_robot_error_code_returns_false(self):
        self.robot.move_ptp.return_value = -1
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertFalse(result)

    def test_move_ptp_exception_returns_false(self):
        self.robot.move_ptp.side_effect = RuntimeError("connection lost")
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # move_linear
    # ------------------------------------------------------------------

    def test_move_linear_success(self):
        self.robot.move_linear.return_value = 0
        result = self.service.move_linear([100, 50, 300, 0, 0, 0], 0, 0, 20, 20)
        self.assertTrue(result)

    def test_move_linear_uses_non_blocking_robot_call_when_not_waiting(self):
        self.robot.move_linear.return_value = 0
        self.service.move_linear([100, 50, 300, 0, 0, 0], 0, 0, 20, 20, wait_to_reach=False)
        _, kwargs = self.robot.move_linear.call_args
        self.assertEqual(kwargs.get("blocking"), False)

    def test_move_linear_accepts_queued_result(self):
        self.robot.move_linear.return_value = 3
        result = self.service.move_linear([100, 50, 300, 0, 0, 0], 0, 0, 20, 20)
        self.assertTrue(result)

    def test_move_linear_blocked_by_safety(self):
        self.safety.get_violations.return_value = ["out of bounds"]
        result = self.service.move_linear([100, 50, 300, 0, 0, 0], 0, 0, 20, 20)
        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_move_linear_passes_blend_radius(self):
        self.robot.move_linear.return_value = 0
        self.service.move_linear([100, 0, 300, 0, 0, 0], 0, 0, 20, 20, blendR=5.0)
        _, kwargs = self.robot.move_linear.call_args
        self.assertEqual(kwargs.get("blend_radius", None) or self.robot.move_linear.call_args[0][5], 5.0)

    def test_move_linear_exception_returns_false(self):
        self.robot.move_linear.side_effect = ConnectionError
        result = self.service.move_linear([100, 0, 300, 0, 0, 0], 0, 0, 20, 20)
        self.assertFalse(result)

    # ------------------------------------------------------------------
    # start_jog
    # ------------------------------------------------------------------

    def test_start_jog_delegates_to_robot(self):
        self.robot.start_jog.return_value = 0
        result = self.service.start_jog(RobotAxis.Z, Direction.PLUS, 5.0)
        self.assertEqual(result, 0)
        self.robot.start_jog.assert_called_once_with(
            RobotAxis.Z, Direction.PLUS, 5.0,
            self.service._jog_vel, self.service._jog_acc
        )

    def test_start_jog_exception_returns_minus_one(self):
        self.robot.start_jog.side_effect = RuntimeError
        result = self.service.start_jog(RobotAxis.X, Direction.MINUS, 1.0)
        self.assertEqual(result, -1)

    # ------------------------------------------------------------------
    # stop_motion
    # ------------------------------------------------------------------

    def test_stop_motion_success(self):
        self.robot.stop_motion.return_value = 0
        self.assertTrue(self.service.stop_motion())

    def test_stop_motion_retries_until_success(self):
        self.robot.stop_motion.side_effect = [-1, -1, 0]
        self.assertTrue(self.service.stop_motion())
        self.assertEqual(self.robot.stop_motion.call_count, 3)

    def test_stop_motion_exception_returns_false(self):
        self.robot.stop_motion.side_effect = RuntimeError
        self.assertFalse(self.service.stop_motion())

    # ------------------------------------------------------------------
    # get_current_position
    # ------------------------------------------------------------------

    def test_get_current_position_delegates_to_robot(self):
        self.robot.get_current_position.return_value = [1.0, 2.0, 3.0, 0, 0, 0]
        result = self.service.get_current_position()
        self.assertEqual(result, [1.0, 2.0, 3.0, 0, 0, 0])

    # ------------------------------------------------------------------
    # _wait_for_position
    # ------------------------------------------------------------------

    def test_wait_for_position_returns_true_when_within_threshold(self):
        self.robot.get_current_position.return_value = [100.0, 0.0, 300.0]
        result = self.service._wait_for_position([100.0, 0.0, 300.0], threshold=2.0, delay=0.01, timeout=1.0)
        self.assertTrue(result)

    def test_wait_for_position_returns_false_on_timeout(self):
        self.robot.get_current_position.return_value = [0.0, 0.0, 0.0]
        result = self.service._wait_for_position([100.0, 0.0, 300.0], threshold=2.0, delay=0.01, timeout=0.05)
        self.assertFalse(result)

    def test_wait_for_position_returns_false_when_cancelled(self):
        self.robot.get_current_position.return_value = [0.0, 0.0, 0.0]
        result = self.service._wait_for_position(
            [100.0, 0.0, 300.0],
            threshold=2.0,
            delay=0.01,
            timeout=1.0,
            cancelled=lambda: True,
        )
        self.assertFalse(result)
