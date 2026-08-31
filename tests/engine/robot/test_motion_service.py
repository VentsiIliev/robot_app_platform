import unittest
import time
from unittest.mock import MagicMock, patch

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.motion_sequence import MotionSequenceSegment
from src.engine.robot.services.motion_service import MotionService
from src.engine.robot.safety import MotionCorridor


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
        self.robot.move_linear.return_value = 0
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertTrue(result)
        self.robot.move_linear.assert_called_once()

    def test_move_ptp_uses_non_blocking_robot_call_when_not_waiting(self):
        self.robot.move_linear.return_value = 0
        self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30, wait_to_reach=False)
        _, kwargs = self.robot.move_linear.call_args
        self.assertEqual(kwargs.get("blocking"), False)

    def test_move_ptp_accepts_queued_result(self):
        self.robot.move_linear.return_value = 2
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertTrue(result)

    def test_move_ptp_blocked_by_safety(self):
        self.safety.get_violations.return_value = ["out of bounds"]
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_move_ptp_robot_error_code_returns_false(self):
        self.robot.move_linear.return_value = -1
        result = self.service.move_ptp([100, 0, 300, 0, 0, 0], 0, 0, 30, 30)
        self.assertFalse(result)

    def test_move_ptp_exception_returns_false(self):
        self.robot.move_linear.side_effect = RuntimeError("connection lost")
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

    def test_move_linear_recovery_can_explicitly_bypass_platform_safety_limits(self):
        self.safety.get_violations.return_value = ["X=-284.08 not in [-250, 450]"]
        self.robot.move_linear.return_value = 0

        result = self.service.move_linear(
            [-284.08, 0, 10, 0, 0, 0], 1, 0, 5, 5,
            allow_collision_recovery=True,
            bypass_safety_limits=True,
        )

        self.assertTrue(result)
        self.robot.move_linear.assert_called_once()
        self.assertTrue(self.robot.move_linear.call_args.kwargs["allow_collision_recovery"])

    def test_move_linear_passes_blend_radius(self):
        self.robot.move_linear.return_value = 0
        self.service.move_linear([100, 0, 300, 0, 0, 0], 0, 0, 20, 20, blendR=5.0)
        _, kwargs = self.robot.move_linear.call_args
        self.assertEqual(kwargs.get("blend_radius", None) or self.robot.move_linear.call_args[0][5], 5.0)

    def test_move_linear_exception_returns_false(self):
        self.robot.move_linear.side_effect = ConnectionError
        result = self.service.move_linear([100, 0, 300, 0, 0, 0], 0, 0, 20, 20)
        self.assertFalse(result)

    def test_fast_linear_blocks_target_outside_platform_safety_limits(self):
        self.safety.get_violations.return_value = ["out of bounds"]

        result = self.service.move_fast_linear(
            position=[100, 50, 300, 0, 0, 0],
            tool=1,
            user=1,
            vel=20,
            acc=20,
        )

        self.assertEqual(result["error"], "platform_safety_violation")
        self.robot.move_fast_linear.assert_not_called()

    def test_subzero_fast_linear_retract_anchors_non_z_axes_to_fresh_pose(self):
        self.robot.get_current_position_fresh.return_value = [100.2, 49.8, -4.0, 1.0, 2.0, 3.0]
        self.robot.move_fast_linear.return_value = {
            "result": 0,
            "success": True,
            "accepted": True,
            "final": True,
            "queued": False,
        }

        result = self.service.move_fast_linear(
            position=[100.0, 50.0, 20.0, 0.0, 0.0, 0.0],
            tool=1,
            user=1,
            vel=20,
            acc=20,
            allow_subzero_retract=True,
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            [100.2, 49.8, 20.0, 1.0, 2.0, 3.0],
            self.robot.move_fast_linear.call_args.kwargs["position"],
        )

    def test_regular_linear_move_below_zero_is_blocked(self):
        result = self.service.move_linear([100, 50, -1, 0, 0, 0], 0, 0, 20, 20)
        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_ptp_move_below_zero_is_blocked(self):
        result = self.service.move_ptp([100, 50, -1, 0, 0, 0], 0, 0, 20, 20)
        self.assertFalse(result)
        self.robot.move_ptp.assert_not_called()

    def test_regular_move_cannot_escape_from_sub_zero_pose(self):
        self.robot.get_current_position_fresh.return_value = [100, 50, -50, 0, 0, 0]

        result = self.service.move_linear([100, 50, 25, 0, 0, 0], 0, 0, 20, 20)

        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_registered_corridor_allows_bounded_sub_zero_linear_move(self):
        self.robot.get_current_position.return_value = [100, 50, 25, 0, 0, 0]
        self.robot.move_linear.return_value = 0
        self.robot.set_motion_passage_closed.return_value = True
        self.service.register_motion_corridor(MotionCorridor(
            corridor_id="test_passage",
            x_min=90,
            x_max=110,
            y_min=40,
            y_max=60,
            z_min=-100,
            entry_z_max=50,
            maximum_velocity=25,
            maximum_acceleration=20,
        ))

        result = self.service.move_linear_in_corridor(
            "test_passage", [100, 50, -50, 0, 0, 0], 0, 0, 25, 20, wait_to_reach=False
        )

        self.assertTrue(result)
        self.robot.move_linear.assert_called_once()
        self.robot.set_motion_passage_closed.assert_called_once_with("test_passage", False)

    def test_corridor_rejects_ptp_by_not_exposing_a_ptp_corridor_operation(self):
        self.assertFalse(hasattr(self.service, "move_ptp_in_corridor"))

    def test_corridor_rejects_target_outside_xy_tunnel(self):
        self.robot.get_current_position.return_value = [100, 50, 25, 0, 0, 0]
        self.service.register_motion_corridor(MotionCorridor(
            corridor_id="test_passage",
            x_min=90,
            x_max=110,
            y_min=40,
            y_max=60,
            z_min=-100,
            entry_z_max=50,
            maximum_velocity=25,
            maximum_acceleration=20,
        ))

        result = self.service.move_linear_in_corridor(
            "test_passage", [120, 50, -50, 0, 0, 0], 0, 0, 25, 20
        )

        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_corridor_allows_linear_retract_back_above_zero(self):
        self.robot.get_current_position.return_value = [100, 50, -50, 0, 0, 0]
        self.robot.move_linear.return_value = 0
        self.robot.set_motion_passage_closed.return_value = True
        self.service.register_motion_corridor(MotionCorridor(
            corridor_id="test_passage",
            x_min=90,
            x_max=110,
            y_min=40,
            y_max=60,
            z_min=-100,
            entry_z_max=50,
            maximum_velocity=25,
            maximum_acceleration=20,
        ))

        result = self.service.move_linear_in_corridor(
            "test_passage", [100, 50, 25, 0, 0, 0], 0, 0, 25, 20
        )

        self.assertTrue(result)
        self.robot.move_linear.assert_called_once()
        self.robot.set_motion_passage_closed.assert_called_once_with("test_passage", True)

    def test_servo_jog_is_stopped_when_live_pose_reaches_zero_floor(self):
        self.robot.start_servo_jog.return_value = 0
        self.robot.get_current_position_fresh.return_value = [100, 50, -0.1, 0, 0, 0]
        self.robot.stop_servo_jog.return_value = 0

        result = self.service.start_servo_jog(RobotAxis.Z, Direction.MINUS, linear_mm_s=10)

        self.assertEqual(result, 0)
        deadline = time.monotonic() + 0.3
        while not self.robot.stop_servo_jog.called and time.monotonic() < deadline:
            time.sleep(0.01)
        self.robot.stop_servo_jog.assert_called_once_with()

    def test_bounded_subzero_servo_descent_bypasses_generic_floor_supervisor(self):
        self.robot.start_servo_jog.return_value = 0
        self.robot.get_current_position_fresh.return_value = [100, 50, -5, 0, 0, 0]

        result = self.service.start_servo_jog(
            RobotAxis.Z,
            Direction.MINUS,
            linear_mm_s=10,
            allow_subzero_descent=True,
        )

        self.assertEqual(result, 0)
        time.sleep(0.05)
        self.robot.stop_servo_jog.assert_not_called()

    def test_pickup_retract_settle_may_cross_floor_from_positive_start(self):
        self.robot.start_servo_jog.return_value = 0
        samples = iter((
            [100, 50, 4.6, 0, 0, 0],
            [100, 50, -0.6, 0, 0, 0],
        ))
        self.robot.get_current_position_fresh.side_effect = lambda: next(
            samples, [100, 50, 0.5, 0, 0, 0]
        )

        result = self.service.start_servo_jog(
            RobotAxis.Z,
            Direction.PLUS,
            linear_mm_s=250.0,
            allow_subzero_retract_settle=True,
            disable_collision_checking=True,
        )

        self.assertEqual(0, result)
        time.sleep(0.08)
        self.robot.stop_servo_jog.assert_not_called()
        self.service.stop_servo_jog()

    def test_pickup_collision_override_does_not_apply_recovery_speed_cap(self):
        self.robot.start_servo_jog.return_value = 0
        self.robot.get_current_position_fresh.return_value = [100, 50, 10, 0, 0, 0]

        result = self.service.start_servo_jog(
            RobotAxis.Z,
            Direction.MINUS,
            linear_mm_s=150.0,
            disable_collision_checking=True,
        )

        self.assertEqual(0, result)
        self.assertEqual(
            150.0, self.robot.start_servo_jog.call_args.kwargs["linear_mm_s"]
        )

    def test_recovery_step_allows_pure_upward_move_while_target_remains_subzero(self):
        current = [100, 50, -1.5, 0, 0, 0]
        target = [100, 50, -0.5, 0, 0, 0]
        self.robot.get_current_position_fresh.return_value = current
        self.robot.move_linear.return_value = 0

        result = self.service.move_linear(
            target, 1, 1, 5, 5,
            allow_subzero_step_recovery=True,
        )

        self.assertTrue(result)
        self.assertTrue(
            self.robot.move_linear.call_args.kwargs["allow_collision_recovery"]
        )

    def test_recovery_step_rejects_lateral_subzero_move(self):
        self.robot.get_current_position_fresh.return_value = [100, 50, -1.5, 0, 0, 0]

        result = self.service.move_linear(
            [101, 50, -0.5, 0, 0, 0], 1, 1, 5, 5,
            allow_subzero_step_recovery=True,
        )

        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_recovery_step_rejects_downward_subzero_move(self):
        self.robot.get_current_position_fresh.return_value = [100, 50, -1.5, 0, 0, 0]

        result = self.service.move_linear(
            [100, 50, -2.5, 0, 0, 0], 1, 1, 5, 5,
            allow_subzero_step_recovery=True,
        )

        self.assertFalse(result)
        self.robot.move_linear.assert_not_called()

    def test_general_collision_recovery_keeps_workspace_checks_and_reaches_driver(self):
        self.robot.move_linear.return_value = 0

        result = self.service.move_linear(
            [101, 50, 25, 0, 0, 0], 1, 1, 5, 5,
            allow_collision_recovery=True,
        )

        self.assertTrue(result)
        self.assertTrue(
            self.robot.move_linear.call_args.kwargs["allow_collision_recovery"]
        )


    # ------------------------------------------------------------------
    # move_sequence
    # ------------------------------------------------------------------

    def test_move_sequence_success(self):
        self.robot.set_active_tool.return_value = True
        self.robot.execute_motion_sequence.return_value = 0
        segments = [
            MotionSequenceSegment([100, 0, 300, 0, 0, 0], 30, 40),
            MotionSequenceSegment([120, 0, 300, 0, 0, 10], 50, 20),
        ]

        result = self.service.move_sequence(segments, 1, 0, wait_to_reach=False)

        self.assertTrue(result)
        self.robot.set_active_tool.assert_called_once_with(1)
        self.robot.execute_motion_sequence.assert_called_once_with(
            segments,
            tool=1,
            user=0,
            blocking=False,
        )

    def test_move_sequence_blocks_on_safety_violation(self):
        self.safety.get_violations.side_effect = [[], ["out of bounds"]]
        segments = [
            MotionSequenceSegment([100, 0, 300, 0, 0, 0], 30, 40),
            MotionSequenceSegment([999, 0, 300, 0, 0, 0], 50, 20),
        ]

        result = self.service.move_sequence(segments, 1, 0)

        self.assertFalse(result)
        self.robot.execute_motion_sequence.assert_not_called()

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
        self.robot.get_current_position.return_value = [100.0, 0.0, 300.0, 0.0, 0.0, 0.0]
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

    def test_wait_for_position_waits_for_orientation_when_target_contains_rpy(self):
        self.robot.get_current_position.return_value = [100.0, 0.0, 300.0, 180.0, 0.0, 0.0]
        result = self.service._wait_for_position(
            [100.0, 0.0, 300.0, 180.0, 0.0, 15.0],
            threshold=2.0,
            orientation_threshold_deg=1.0,
            delay=0.01,
            timeout=0.05,
        )
        self.assertFalse(result)

    def test_wait_for_position_accepts_orientation_when_within_wrapped_threshold(self):
        self.robot.get_current_position.return_value = [100.0, 0.0, 300.0, 180.0, 0.0, -179.5]
        result = self.service._wait_for_position(
            [100.0, 0.0, 300.0, 180.0, 0.0, 179.8],
            threshold=2.0,
            orientation_threshold_deg=1.0,
            delay=0.01,
            timeout=1.0,
        )
        self.assertTrue(result)
