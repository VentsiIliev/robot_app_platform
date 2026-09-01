import threading
import time
import unittest

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.procedures import (
    ServoUntilConditionConfig,
    ServoUntilConditionProcedure,
    ServoRetractConfig,
    TimedDummyPickupCondition,
    VacuumPickupCondition,
)


class FakeRobot:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.stop_restore_collision = []
        self.start_return = 0

    def start_servo_jog(
        self,
        axis,
        direction,
        linear_mm_s=None,
        angular_deg_s=None,
        *,
        frame="user",
        tool=0,
        user=0,
        allow_subzero_descent=False,
        allow_subzero_retract_settle=False,
        disable_collision_checking=False,
    ):
        self.started.append(
            {
                "axis": axis,
                "direction": direction,
                "linear_mm_s": linear_mm_s,
                "angular_deg_s": angular_deg_s,
                "frame": frame,
                "tool": tool,
                "user": user,
                "allow_subzero_descent": allow_subzero_descent,
                "allow_subzero_retract_settle": allow_subzero_retract_settle,
                "disable_collision_checking": disable_collision_checking,
            }
        )
        return self.start_return

    def stop_servo_jog(self, *, restore_collision_checking=True):
        self.stopped += 1
        self.stop_restore_collision.append(restore_collision_checking)
        return 0

    def controlled_stop(self, expected_task_id):
        self.stopped += 1
        return {
            "result": 0,
            "success": True,
            "stopped": True,
            "expected_task_id": expected_task_id,
            "future_work_preserved": True,
        }


class ManualCondition:
    def __init__(self):
        self.active = False

    def is_active(self):
        return self.active


class _ConditionSequence:
    def __init__(self, *values):
        self._values = list(values)

    def __call__(self):
        if len(self._values) > 1:
            return self._values.pop(0)
        return self._values[0]


class FailingCondition:
    def is_active(self):
        raise RuntimeError("sensor disconnected")


class FailsAfterStartCondition:
    def __init__(self):
        self.calls = 0

    def is_active(self):
        self.calls += 1
        if self.calls <= 2:
            return False
        raise RuntimeError("sensor disconnected")


class UnhealthyVacuumSensor:
    def is_vacuum_detected(self):
        return False

    def is_healthy(self):
        return False


class TestServoUntilConditionProcedure(unittest.TestCase):
    def test_descending_servo_switches_from_fast_to_contact_speed_and_captures_pose(self):
        class TransitionRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.positions = [
                    [0.0, 0.0, 100.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 60.0, 0.0, 0.0, 0.0],
                    [0.0, 0.0, 49.0, 0.0, 0.0, 0.0],
                ]

            def get_current_position(self):
                if len(self.positions) > 1:
                    return self.positions.pop(0)
                return list(self.positions[0])

            def stop_motion(self):
                return True

        robot = TransitionRobot()
        result = ServoUntilConditionProcedure(
            robot,
            _ConditionSequence(False, False, False, False, True),
        ).run(
            config=ServoUntilConditionConfig(
                linear_mm_s=10.0,
                initial_linear_mm_s=100.0,
                slowdown_z_mm=50.0,
                minimum_z_mm=0.0,
                poll_interval_s=0.001,
                timeout_s=0.1,
            )
        )

        self.assertTrue(result.success)
        self.assertEqual([100.0, 10.0], [item["linear_mm_s"] for item in robot.started])
        self.assertEqual(2, robot.stopped)
        self.assertEqual(49.0, result.contact_pose[2])

    def test_successful_detection_retracts_up_to_reference_z(self):
        class RetractRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [10.0, 20.0, 40.0, 180.0, 0.0, 0.0]

            def start_servo_jog(self, axis, direction, *args, **kwargs):
                ret = super().start_servo_jog(axis, direction, *args, **kwargs)
                if direction == Direction.PLUS:
                    self.position[2] = 100.0
                return ret

            def get_current_position(self):
                return list(self.position)

            def stop_motion(self):
                return True

        robot = RetractRobot()
        condition = _ConditionSequence(False, False, True)
        result = ServoUntilConditionProcedure(robot, condition).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                target_pose=[0.0, 0.0, 100.0, 0.0, 0.0, 0.0],
                linear_mm_s=10.0,
                poll_interval_s=0.005,
                timeout_s=0.1,
                position_tolerance_mm=0.5,
            ),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.retracted)
        self.assertEqual([Direction.MINUS, Direction.PLUS], [item["direction"] for item in robot.started])
        self.assertEqual(2, robot.stopped)

    def test_scoped_collision_override_applies_to_descent_and_retract(self):
        class RetractRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 40.0, 0.0, 0.0, 0.0]

            def start_servo_jog(self, axis, direction, *args, **kwargs):
                result = super().start_servo_jog(axis, direction, *args, **kwargs)
                if direction == Direction.PLUS:
                    self.position[2] += 10.0
                return result

            def get_current_position(self):
                return list(self.position)

            def stop_motion(self):
                return True

        robot = RetractRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.001,
                timeout_s=0.1,
                disable_collision_checking=True,
            ),
            retract=ServoRetractConfig(
                distance_mm=10.0,
                linear_mm_s=25.0,
                poll_interval_s=0.001,
                timeout_s=0.1,
                maximum_distance_mm=20.0,
            ),
        )

        self.assertTrue(result.success)
        self.assertEqual(2, len(robot.started))
        self.assertTrue(all(item["disable_collision_checking"] for item in robot.started))
        self.assertEqual(2, robot.stopped)
        self.assertEqual([False, True], robot.stop_restore_collision)

    def test_distance_retract_accepts_overshoot_within_clearance_window(self):
        class RetractRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 40.0, 0.0, 0.0, 0.0]

            def start_servo_jog(self, axis, direction, *args, **kwargs):
                ret = super().start_servo_jog(axis, direction, *args, **kwargs)
                if direction == Direction.PLUS:
                    self.position[2] += 25.0
                return ret

            def get_current_position(self):
                return list(self.position)

            def stop_motion(self):
                return True

        robot = RetractRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                distance_mm=10.0,
                linear_mm_s=250.0,
                poll_interval_s=0.005,
                timeout_s=0.1,
                maximum_distance_mm=30.0,
            ),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.retracted)

    def test_target_pose_retract_computes_limit_from_required_distance_and_margin(self):
        class RetractRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 42.9, 0.0, 0.0, 0.0]

            def start_servo_jog(self, axis, direction, *args, **kwargs):
                ret = super().start_servo_jog(axis, direction, *args, **kwargs)
                if direction == Direction.PLUS:
                    speed = float(kwargs["linear_mm_s"])
                    self.position[2] = 95.0 if speed == 250.0 else 110.021
                return ret

            def get_current_position(self):
                return list(self.position)

            def stop_motion(self):
                return True

        robot = RetractRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                target_pose=[0.0, 0.0, 110.021, 0.0, 0.0, 0.0],
                linear_mm_s=250.0,
                poll_interval_s=0.005,
                timeout_s=0.1,
                maximum_distance_mm=50.0,
                safety_margin_mm=10.0,
                final_linear_mm_s=50.0,
                slowdown_distance_mm=20.0,
            ),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.retracted)
        retract_speeds = [
            item["linear_mm_s"]
            for item in robot.started
            if item["direction"] == Direction.PLUS
        ]
        self.assertEqual([250.0, 50.0], retract_speeds)

    def test_target_pose_retract_delegates_hard_bound_to_robot_runtime(self):
        class BoundedRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 42.9, 0.0, 0.0, 0.0]
                self.bounded_request = None

            def get_current_position(self):
                return list(self.position)

            def servo_jog_to_z(self, **kwargs):
                self.bounded_request = kwargs
                self.position[2] = kwargs["target_z_mm"]
                return {"success": True, "target_z": kwargs["target_z_mm"], "final_z": self.position[2]}

        robot = BoundedRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                target_pose=[0.0, 0.0, 110.021, 0.0, 0.0, 0.0],
                linear_mm_s=350.0,
                final_linear_mm_s=50.0,
                slowdown_distance_mm=20.0,
                safety_margin_mm=10.0,
                poll_interval_s=0.005,
                timeout_s=0.1,
            ),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.retracted)
        self.assertEqual(110.021, robot.bounded_request["target_z_mm"])
        self.assertAlmostEqual(77.121, robot.bounded_request["maximum_distance_mm"])
        self.assertEqual([Direction.MINUS], [item["direction"] for item in robot.started])

    def test_fast_lin_retract_requires_final_success_and_verifies_target_z(self):
        class FastLinRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [1.0, 2.0, 5.0, 180.0, 0.0, 7.0]
                self.fast_linear_request = None

            def get_current_position(self):
                return list(self.position)

            def move_fast_linear(self, **kwargs):
                self.fast_linear_request = kwargs
                self.position = list(kwargs["position"])
                return {
                    "result": 0,
                    "success": True,
                    "accepted": True,
                    "final": True,
                    "queued": False,
                }

        robot = FastLinRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=0.1,
                tool=1,
                user=2,
            ),
            retract=ServoRetractConfig(
                target_pose=[9.0, 9.0, 35.0, 0.0, 0.0, 0.0],
                motion_type="fast_lin",
                position_tolerance_mm=0.5,
                safety_margin_mm=10.0,
                fast_lin_velocity_percent=70.0,
                fast_lin_acceleration_percent=40.0,
            ),
        )

        self.assertTrue(result.success)
        self.assertTrue(result.retracted)
        self.assertEqual(robot.fast_linear_request["position"], [9.0, 9.0, 35.0, 0.0, 0.0, 0.0])
        self.assertEqual(robot.fast_linear_request["tool"], 1)
        self.assertEqual(robot.fast_linear_request["user"], 2)
        self.assertEqual(robot.fast_linear_request["vel"], 70.0)
        self.assertEqual(robot.fast_linear_request["acc"], 40.0)

    def test_fast_lin_retract_waits_for_delayed_final_pose_feedback(self):
        class DelayedFeedbackRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position_reads = 0

            def get_current_position(self):
                self.position_reads += 1
                if self.position_reads < 5:
                    return [0.0, 0.0, 5.0, 0.0, 0.0, 0.0]
                return [9.0, 9.0, 35.0, 0.0, 0.0, 0.0]

            def move_fast_linear(self, **_kwargs):
                return {
                    "result": 0,
                    "success": True,
                    "accepted": True,
                    "final": True,
                    "queued": False,
                }

        result = ServoUntilConditionProcedure(
            DelayedFeedbackRobot(), _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                target_pose=[9.0, 9.0, 35.0, 0.0, 0.0, 0.0],
                motion_type="fast_lin",
                poll_interval_s=0.005,
                timeout_s=0.1,
            ),
        )

        self.assertTrue(result.success, result.message)

    def test_fast_lin_retract_accepts_non_final_response_and_waits_for_pose(self):
        class FastLinRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 5.0, 0.0, 0.0, 0.0]

            def get_current_position(self):
                return list(self.position)

            def move_fast_linear(self, **kwargs):
                self.position = list(kwargs["position"])
                return {
                    "result": 1,
                    "success": True,
                    "accepted": True,
                    "final": False,
                    "queued": True,
                    "queue_position": 1,
                    "task_id": 23,
                }

        result = ServoUntilConditionProcedure(
            FastLinRobot(), _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                target_pose=[0.0, 0.0, 35.0, 0.0, 0.0, 0.0],
                motion_type="fast_lin",
                safety_margin_mm=10.0,
            ),
        )

        self.assertTrue(result.success, result.message)
        self.assertTrue(result.retracted)

    def test_distance_retract_delegates_computed_target_and_notifies_planning_hook(self):
        class BoundedRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [1.0, 2.0, 42.9, 0.0, 0.0, 3.0]
                self.bounded_request = None

            def get_current_position(self):
                return list(self.position)

            def servo_jog_to_z(self, **kwargs):
                self.bounded_request = kwargs
                self.position[2] = kwargs["target_z_mm"]
                return {"success": True, "final_z": self.position[2]}

        robot = BoundedRobot()
        planning_starts = []
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(poll_interval_s=0.005, timeout_s=0.1),
            retract=ServoRetractConfig(
                distance_mm=20.0,
                linear_mm_s=100.0,
                final_linear_mm_s=20.0,
                slowdown_distance_mm=10.0,
                safety_margin_mm=5.0,
            ),
            on_retract_start=lambda pose, target_z: planning_starts.append((pose, target_z)),
        )

        self.assertTrue(result.success)
        self.assertAlmostEqual(62.9, robot.bounded_request["target_z_mm"])
        self.assertAlmostEqual(25.0, robot.bounded_request["maximum_distance_mm"])
        self.assertEqual(1, len(planning_starts))
        self.assertAlmostEqual(62.9, planning_starts[0][1])

    def test_stops_servo_when_condition_becomes_active(self):
        robot = FakeRobot()
        condition = ManualCondition()
        procedure = ServoUntilConditionProcedure(robot, condition)
        result_holder = {}

        def run():
            result_holder["result"] = procedure.run(
                config=ServoUntilConditionConfig(
                    axis=RobotAxis.Z,
                    direction=Direction.MINUS,
                    linear_mm_s=12.5,
                    poll_interval_s=0.005,
                    timeout_s=1.0,
                    tool=1,
                    user=0,
                )
            )

        thread = threading.Thread(target=run)
        thread.start()
        time.sleep(0.03)
        condition.active = True
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        result = result_holder["result"]
        self.assertTrue(result.success)
        self.assertTrue(result.detected)
        self.assertFalse(result.timed_out)
        self.assertEqual(robot.stopped, 1)
        self.assertEqual(robot.started[0]["axis"], RobotAxis.Z)
        self.assertEqual(robot.started[0]["direction"], Direction.MINUS)
        self.assertEqual(robot.started[0]["linear_mm_s"], 12.5)
        self.assertEqual(robot.started[0]["tool"], 1)

    def test_bounded_contact_search_can_authorize_subzero_descent(self):
        robot = FakeRobot()
        condition = _ConditionSequence(False, False, True)

        result = ServoUntilConditionProcedure(robot, condition).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.001,
                timeout_s=0.1,
                allow_subzero_descent=True,
            )
        )

        self.assertTrue(result.success)
        self.assertTrue(robot.started[0]["allow_subzero_descent"])

    def test_stops_servo_on_timeout(self):
        robot = FakeRobot()
        procedure = ServoUntilConditionProcedure(robot, lambda: False)

        result = procedure.run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=0.02,
            )
        )

        self.assertFalse(result.success)
        self.assertFalse(result.detected)
        self.assertTrue(result.timed_out)
        self.assertEqual(robot.stopped, 1)

    def test_stops_servo_when_stop_guard_triggers(self):
        robot = FakeRobot()
        guard_calls = 0

        def z_limit_reached():
            nonlocal guard_calls
            guard_calls += 1
            return guard_calls >= 2

        result = ServoUntilConditionProcedure(robot, lambda: False).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=1.0,
            ),
            stop_guard=z_limit_reached,
        )

        self.assertFalse(result.success)
        self.assertTrue(result.guard_triggered)
        self.assertEqual(result.message, "stop_guard_triggered")
        self.assertEqual(robot.stopped, 1)

    def test_stops_servo_at_maximum_travel(self):
        class MovingRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 50.0, 0.0, 0.0, 0.0]

            def get_current_position(self):
                position = list(self.position)
                if self.started:
                    self.position[2] -= 6.0
                return position

        robot = MovingRobot()
        result = ServoUntilConditionProcedure(robot, lambda: False).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.001,
                timeout_s=1.0,
                maximum_travel_mm=10.0,
            )
        )

        self.assertFalse(result.success)
        self.assertTrue(result.guard_triggered)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.message, "maximum_travel_reached")
        self.assertEqual(robot.stopped, 1)

    def test_stops_servo_at_configured_minimum_z(self):
        class DescendingRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.position = [0.0, 0.0, 5.0, 0.0, 0.0, 0.0]

            def get_current_position(self):
                position = list(self.position)
                if self.started:
                    self.position[2] -= 3.0
                return position

        robot = DescendingRobot()
        result = ServoUntilConditionProcedure(robot, lambda: False).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.001,
                timeout_s=1.0,
                minimum_z_mm=-1.0,
            )
        )

        self.assertFalse(result.success)
        self.assertTrue(result.guard_triggered)
        self.assertFalse(result.timed_out)
        self.assertEqual(result.message, "minimum_z_reached")
        self.assertEqual(robot.stopped, 1)

    def test_stops_servo_when_stop_guard_cannot_be_read(self):
        robot = FakeRobot()

        def unreadable_guard():
            raise RuntimeError("position unavailable")

        result = ServoUntilConditionProcedure(robot, lambda: False).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=1.0,
            ),
            stop_guard=unreadable_guard,
        )

        self.assertFalse(result.success)
        self.assertTrue(result.guard_triggered)
        self.assertEqual(result.message, "stop_guard_unreadable")
        self.assertEqual(robot.stopped, 1)

    def test_does_not_start_servo_when_condition_already_active(self):
        robot = FakeRobot()
        procedure = ServoUntilConditionProcedure(robot, lambda: True)

        result = procedure.run(config=ServoUntilConditionConfig(timeout_s=0.02))

        self.assertTrue(result.success)
        self.assertTrue(result.detected)
        self.assertEqual(result.message, "condition_already_active")
        self.assertEqual(robot.started, [])
        self.assertEqual(robot.stopped, 0)

    def test_does_not_start_servo_when_condition_unreadable_in_preflight(self):
        robot = FakeRobot()
        procedure = ServoUntilConditionProcedure(robot, FailingCondition())

        result = procedure.run(
            config=ServoUntilConditionConfig(
                timeout_s=0.02,
                poll_interval_s=0.005,
                preflight_condition_read_attempts=2,
            )
        )

        self.assertFalse(result.success)
        self.assertTrue(result.condition_failed)
        self.assertEqual(result.message, "condition_unreadable_before_motion")
        self.assertEqual(robot.started, [])
        self.assertEqual(robot.stopped, 0)

    def test_unhealthy_vacuum_sensor_blocks_servo_start(self):
        robot = FakeRobot()
        result = ServoUntilConditionProcedure(
            robot,
            VacuumPickupCondition(UnhealthyVacuumSensor()),
        ).run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=0.02,
                preflight_condition_read_attempts=1,
            )
        )

        self.assertFalse(result.success)
        self.assertTrue(result.condition_failed)
        self.assertEqual(result.message, "condition_unreadable_before_motion")
        self.assertEqual(robot.started, [])

    def test_stops_servo_when_condition_becomes_unreadable_during_motion(self):
        robot = FakeRobot()
        procedure = ServoUntilConditionProcedure(robot, FailsAfterStartCondition())

        result = procedure.run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=1.0,
                condition_read_failure_limit=2,
            )
        )

        self.assertFalse(result.success)
        self.assertTrue(result.condition_failed)
        self.assertEqual(result.message, "condition_unreadable_during_servo")
        self.assertEqual(len(robot.started), 1)
        self.assertEqual(robot.stopped, 1)

    def test_invalid_linear_speed_blocks_servo_start(self):
        robot = FakeRobot()
        procedure = ServoUntilConditionProcedure(robot, lambda: False)

        result = procedure.run(
            config=ServoUntilConditionConfig(
                axis=RobotAxis.Z,
                linear_mm_s=0.0,
            )
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, "invalid_linear_speed")
        self.assertEqual(robot.started, [])
        self.assertEqual(robot.stopped, 0)

    def test_invalid_maximum_travel_blocks_servo_start(self):
        robot = FakeRobot()
        result = ServoUntilConditionProcedure(robot, lambda: False).run(
            config=ServoUntilConditionConfig(maximum_travel_mm=0.0)
        )

        self.assertFalse(result.success)
        self.assertEqual(result.message, "invalid_maximum_travel")
        self.assertEqual(robot.started, [])

    def test_timed_dummy_condition_arms_only_after_servo_start(self):
        robot = FakeRobot()
        condition = TimedDummyPickupCondition(detect_after_s=0.0)
        procedure = ServoUntilConditionProcedure(robot, condition)

        result = procedure.run(
            config=ServoUntilConditionConfig(
                poll_interval_s=0.005,
                timeout_s=0.1,
            )
        )

        self.assertTrue(result.success)
        self.assertTrue(result.detected)
        self.assertEqual(result.message, "condition_detected")
        self.assertEqual(len(robot.started), 1)
        self.assertEqual(robot.stopped, 1)

    def test_ros_managed_mode_waits_for_terminal_stationary_state(self):
        class ManagedRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.operation_id = "managed-1"
                self.state = "moving"
                self.sensor_events = []

            def start_conditional_servo(self, request):
                self.request = request
                return {
                    "success": True,
                    "conditional_servo": {
                        "operation_id": self.operation_id,
                        "state": "moving",
                    },
                }

            def publish_conditional_servo_sensor(self, **event):
                self.sensor_events.append(event)
                if event["state"]:
                    # The ROS supervisor only exposes this terminal state after
                    # local stop and stationary joint-state confirmation.
                    self.state = "condition_met"
                return True

            def get_conditional_servo_status(self):
                return {
                    "operation_id": self.operation_id,
                    "state": self.state,
                    "trigger_monotonic_ns": 10,
                    "stop_command_completed_monotonic_ns": 20,
                    "stopped_monotonic_ns": 30,
                }

            def cancel_conditional_servo(self):
                self.state = "cancelled"
                return True

        robot = ManagedRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, False, True)
        ).run(config=ServoUntilConditionConfig(
            execution_mode="ros_managed",
            poll_interval_s=0.001,
            timeout_s=0.1,
        ))

        self.assertTrue(result.success)
        self.assertTrue(result.detected)
        self.assertEqual(result.message, "condition_detected")
        self.assertEqual(robot.started, [])
        self.assertEqual([False, True], [event["state"] for event in robot.sensor_events])
        self.assertTrue(robot.sensor_events[-1]["detected_monotonic_ns"] > 0)

    def test_ros_managed_mode_fails_without_capabilities_and_never_starts_legacy_servo(self):
        robot = FakeRobot()

        result = ServoUntilConditionProcedure(robot, lambda: False).run(
            config=ServoUntilConditionConfig(execution_mode="ros_managed")
        )

        self.assertFalse(result.success)
        self.assertTrue(result.start_failed)
        self.assertEqual(
            result.message,
            "ros_managed_unavailable:missing_capabilities:start,publish_sensor,status,cancel",
        )
        self.assertEqual(robot.started, [])

    def test_sensor_controlled_fast_lin_moves_to_minimum_z_without_starting_servo(self):
        class DiagnosticRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.pose = [1.0, 2.0, 80.0, 4.0, 5.0, 6.0]
                self.fast_linear_request = None

            def get_current_position(self):
                return list(self.pose)

            def move_fast_linear(self, **kwargs):
                self.fast_linear_request = kwargs
                self.pose = list(kwargs["position"])
                return {
                    "result": 0,
                    "success": True,
                    "accepted": True,
                    "final": False,
                    "queued": True,
                    "task_id": 17,
                }

            def stop_motion(self):
                self.stopped += 1
                return True

        robot = DiagnosticRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(config=ServoUntilConditionConfig(
            execution_mode="sensor_controlled_fast_lin",
            minimum_z_mm=50.0,
            approach_velocity=10.0,
            approach_acceleration=10.0,
            tool=1,
            user=2,
        ))

        self.assertTrue(result.success)
        self.assertEqual(result.message, "sensor_controlled_fast_lin_detected")
        self.assertEqual(robot.started, [])
        self.assertEqual(robot.fast_linear_request["position"], [1.0, 2.0, 50.0, 4.0, 5.0, 6.0])
        self.assertEqual(robot.fast_linear_request["vel"], 10.0)
        self.assertEqual(robot.fast_linear_request["acc"], 10.0)
        self.assertFalse(robot.fast_linear_request["blocking"])
        self.assertEqual(robot.stopped, 1)

    def test_sensor_controlled_fast_lin_waits_for_stopped_task_to_become_inactive(self):
        class DiagnosticRobot(FakeRobot):
            def __init__(self):
                super().__init__()
                self.pose = [1.0, 2.0, 80.0, 4.0, 5.0, 6.0]
                self.status_reads = 0
                self.retract_started_after_status_reads = None

            def get_current_position(self):
                return list(self.pose)

            def get_execution_status(self):
                self.status_reads += 1
                if self.status_reads < 3:
                    return {
                        "is_executing": False,
                        "current_task_id": None,
                        "last_completed_task_id": 16,
                        "state": "idle",
                    }
                if self.status_reads < 5:
                    return {"is_executing": True, "current_task_id": 17, "state": "stopping"}
                return {
                    "is_executing": False,
                    "current_task_id": None,
                    "last_completed_task_id": 17,
                    "state": "idle",
                }

            def move_fast_linear(self, **kwargs):
                if kwargs["position"][2] == 50.0:
                    return {
                        "result": 0, "success": True, "accepted": True,
                        "final": False, "queued": False, "task_id": 17,
                    }
                self.retract_started_after_status_reads = self.status_reads
                self.pose = list(kwargs["position"])
                return {
                    "result": 0, "success": True, "accepted": True,
                    "final": False, "queued": False, "task_id": 18,
                }

            def stop_motion(self):
                return True

        robot = DiagnosticRobot()
        result = ServoUntilConditionProcedure(
            robot, _ConditionSequence(False, False, True)
        ).run(
            config=ServoUntilConditionConfig(
                execution_mode="sensor_controlled_fast_lin",
                minimum_z_mm=50.0,
                poll_interval_s=0.001,
                timeout_s=0.2,
            ),
            retract=ServoRetractConfig(
                target_pose=[1.0, 2.0, 100.0, 4.0, 5.0, 6.0],
                motion_type="fast_lin",
                poll_interval_s=0.001,
                timeout_s=0.2,
            ),
        )

        self.assertTrue(result.success, result.message)
        self.assertGreaterEqual(robot.retract_started_after_status_reads, 6)


if __name__ == "__main__":
    unittest.main()
