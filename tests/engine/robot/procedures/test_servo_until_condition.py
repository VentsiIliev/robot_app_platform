import threading
import time
import unittest

from src.engine.robot.enums.axis import Direction, RobotAxis
from src.engine.robot.procedures import (
    ServoUntilConditionConfig,
    ServoUntilConditionProcedure,
)


class FakeRobot:
    def __init__(self):
        self.started = []
        self.stopped = 0
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
            }
        )
        return self.start_return

    def stop_servo_jog(self):
        self.stopped += 1
        return 0


class ManualCondition:
    def __init__(self):
        self.active = False

    def is_active(self):
        return self.active


class TestServoUntilConditionProcedure(unittest.TestCase):
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

    def test_does_not_start_servo_when_condition_already_active(self):
        robot = FakeRobot()
        procedure = ServoUntilConditionProcedure(robot, lambda: True)

        result = procedure.run(config=ServoUntilConditionConfig(timeout_s=0.02))

        self.assertTrue(result.success)
        self.assertTrue(result.detected)
        self.assertEqual(result.message, "condition_already_active")
        self.assertEqual(robot.started, [])
        self.assertEqual(robot.stopped, 0)


if __name__ == "__main__":
    unittest.main()
