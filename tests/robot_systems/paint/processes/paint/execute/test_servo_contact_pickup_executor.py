import unittest
import sys
import types
from types import SimpleNamespace

paint_package = types.ModuleType("src.robot_systems.paint")
paint_package.__path__ = ["/home/ilv/Desktop/robot_app_platform/src/robot_systems/paint"]
sys.modules.setdefault("src.robot_systems.paint", paint_package)
execute_package = types.ModuleType("src.robot_systems.paint.processes.paint.execute")
execute_package.__path__ = ["/home/ilv/Desktop/robot_app_platform/src/robot_systems/paint/processes/paint/execute"]
sys.modules.setdefault("src.robot_systems.paint.processes.paint.execute", execute_package)

from src.robot_systems.paint.processes.paint.execute.pickup_executor import (
    PaintPickupExecutor,
    PickupPlan,
    PickupWaypoint,
)


class _FakeRobot:
    def __init__(self):
        self.started = []
        self.stopped = 0

    def start_servo_jog(self, *args, **kwargs):
        self.started.append((args, kwargs))
        return 0

    def stop_servo_jog(self):
        self.stopped += 1
        return 0


class _FakeMotion:
    def __init__(self):
        self.vacuum_on = 0
        self.sequences = []

    def turn_vacuum_on(self):
        self.vacuum_on += 1
        return True, ""

    def move_ordered_pickup_sequence(self, label, segments):
        self.sequences.append((label, segments))
        return True


class _ConditionAfterStart:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return self.calls >= 3


class ServoContactPickupExecutorTest(unittest.TestCase):
    def test_servo_contact_pickup_splits_approach_and_remaining_segments(self):
        robot = _FakeRobot()
        motion = _FakeMotion()
        pickup_motion = SimpleNamespace(
            servo_contact_linear_mm_s=12.0,
            servo_contact_timeout_s=1.0,
            servo_contact_poll_interval_s=0.01,
            servo_contact_preflight_read_attempts=2,
            servo_contact_read_failure_limit=3,
            servo_contact_fallback_to_planned_descend=False,
        )
        owner = SimpleNamespace(
            _robot_service=robot,
            _motion=motion,
            _pickup_condition=_ConditionAfterStart(),
            _pickup_tool=1,
            _pickup_user=0,
            _paint_process_config=lambda: SimpleNamespace(pickup_motion=pickup_motion),
        )
        executor = PaintPickupExecutor(owner)
        plan = PickupPlan(
            strategy_name="test",
            motion_plan=object(),
            waypoints=(
                PickupWaypoint("approach", [0, 0, 100, 0, 0, 0], 10, 10, "ptp", 0),
                PickupWaypoint("planned descend", [0, 0, 0, 0, 0, 0], 10, 10, "linear", 0),
                PickupWaypoint("lift", [0, 0, 50, 0, 0, 0], 10, 10, "ptp", 0),
                PickupWaypoint("stage", [10, 0, 50, 0, 0, 0], 10, 10, "ptp", 0),
            ),
            vacuum_on_before_moves=True,
            servo_contact_enabled=True,
            contact_waypoint_index=1,
        )

        self.assertTrue(executor._execute_servo_contact_pickup_sequence(plan))

        self.assertEqual(motion.vacuum_on, 1)
        self.assertEqual(robot.stopped, 1)
        self.assertEqual(
            [label for label, _segments in motion.sequences],
            [
                "Pickup approach before servo contact",
                "Pickup lift and staging after servo contact",
            ],
        )
        moved_labels = [
            segment["label"]
            for _label, segments in motion.sequences
            for segment in segments
        ]
        self.assertEqual(moved_labels, ["approach", "lift", "stage"])
        self.assertEqual(robot.started[0][1]["linear_mm_s"], 12.0)


if __name__ == "__main__":
    unittest.main()
