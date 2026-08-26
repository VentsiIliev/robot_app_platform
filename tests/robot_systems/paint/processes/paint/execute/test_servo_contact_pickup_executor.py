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
    build_magazine_pickup_release_segments,
    build_paint_pickup_segments,
)
from src.robot_systems.paint.processes.paint.config import (
    PICKUP_CONTACT_MODE_HEIGHT_MEASURE,
    PICKUP_CONTACT_MODE_PLANNED,
    PICKUP_CONTACT_MODE_SERVO_CONTACT,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    _execute_magazine_servo_contact_pickup_release,
)


class _FakeRobot:
    def __init__(self):
        self.started = []
        self.stopped = 0
        self.ptp_moves = []
        self.position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        self.support_prepared = False
        self.prepared = []
        self.executed_prepared = []
        self.discarded_prepared = []
        self.ptp_return = True

    def start_servo_jog(self, *args, **kwargs):
        self.started.append((args, kwargs))
        direction = kwargs.get("direction", args[1] if len(args) > 1 else None)
        if getattr(direction, "name", "") == "PLUS":
            self.position[2] += 10.0
        return 0

    def stop_servo_jog(self):
        self.stopped += 1
        return 0

    def stop_motion(self):
        return True

    def get_current_position(self):
        return list(self.position)

    def move_ptp(self, position, *args, **kwargs):
        self.ptp_moves.append((list(position), args, kwargs))
        self.position = list(position)
        return self.ptp_return

    def prepare_ordered_motion_chain(self, segments, start_position, tool, user):
        if not self.support_prepared:
            return None
        self.prepared.append((segments, list(start_position), tool, user))
        return {"plan_id": "prepared-1"}

    def execute_prepared_ordered_motion_chain(self, plan_id):
        self.executed_prepared.append(plan_id)
        return {"success": True, "state": "completed", "result": 0}

    def discard_prepared_ordered_motion_chain(self, _plan_id):
        self.discarded_prepared.append(_plan_id)
        return {"success": True}


class _FakeMotion:
    def __init__(self):
        self.vacuum_on = 0
        self.sequences = []

    def turn_vacuum_on(self, *, required=False):
        self.vacuum_on += 1
        self.vacuum_required = required
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
    def test_magazine_servo_handoff_executes_clearance_and_release_as_one_chain(self):
        robot = _FakeRobot()
        robot.support_prepared = True
        motion = _FakeMotion()
        pickup_motion = SimpleNamespace(
            servo_contact_linear_mm_s=100.0,
            servo_contact_min_z_mm=-5.0,
            servo_contact_timeout_s=1.0,
            servo_contact_poll_interval_s=0.01,
            servo_contact_preflight_read_attempts=2,
            servo_contact_read_failure_limit=3,
            servo_contact_retract_distance_mm=10.0,
            servo_contact_retract_linear_mm_s=250.0,
            lift_align_vel_percent=30.0,
            lift_align_acc_percent=30.0,
        )
        owner = SimpleNamespace(
            _robot_service=robot,
            _motion=motion,
            _pickup_condition=_ConditionAfterStart(),
            _pickup_tool=1,
            _pickup_user=0,
            _paint_process_config=lambda: SimpleNamespace(pickup_motion=pickup_motion),
        )
        waypoints = (
            ("approach", [1, 2, 100, 0, 0, 3], 10, 10, "ptp", 0),
            ("contact", [1, 2, 0, 0, 0, 3], 10, 10, "linear", 0),
            ("lift", [1, 2, 50, 0, 0, 3], 30, 30, "ptp", 20),
            ("release", [20, 30, 40, 0, 0, 0], 25, 25, "ptp", 0),
        )

        ok, message = _execute_magazine_servo_contact_pickup_release(
            owner,
            waypoints,
            retract_reference_pose=[9, 9, 100, 0, 0, 0],
            release_label="calibration",
        )

        self.assertTrue(ok, message)
        self.assertEqual(robot.ptp_moves, [])
        self.assertEqual(robot.prepared[0][1], [0.0, 0.0, 10.0, 0.0, 0.0, 0.0])
        self.assertEqual(
            [segment["label"] for segment in robot.prepared[0][0]],
            ["Raising magazine workpiece to safe transfer clearance", "release"],
        )
        self.assertEqual(robot.prepared[0][0][0]["position"], [1, 2, 100.0, 0, 0, 3])
        self.assertEqual(robot.prepared[0][0][0]["blendR"], 20.0)
        self.assertEqual(robot.executed_prepared, ["prepared-1"])
        self.assertEqual(robot.started[1][1]["linear_mm_s"], 250.0)
        self.assertTrue(robot.started[0][1]["disable_collision_checking"])
        self.assertTrue(robot.started[1][1]["disable_collision_checking"])

    def test_planned_pickup_keeps_full_existing_waypoint_sequence(self):
        motion = _FakeMotion()
        owner = SimpleNamespace(_motion=motion)
        plan = PickupPlan(
            strategy_name="planned-test",
            motion_plan=object(),
            waypoints=(
                PickupWaypoint("approach", [0, 0, 100, 0, 0, 0], 10, 10),
                PickupWaypoint("descend", [0, 0, 0, 0, 0, 0], 10, 10),
                PickupWaypoint("lift", [0, 0, 50, 0, 0, 0], 10, 10),
                PickupWaypoint("stage", [10, 0, 50, 0, 0, 0], 10, 10),
            ),
            vacuum_on_before_moves=False,
            contact_mode=PICKUP_CONTACT_MODE_PLANNED,
        )

        self.assertTrue(PaintPickupExecutor(owner)._execute_custom_pickup_sequence(plan))
        self.assertEqual(
            ["approach", "descend", "lift", "stage"],
            [segment["label"] for segment in motion.sequences[0][1]],
        )

    def test_servo_contact_pickup_splits_approach_and_remaining_segments(self):
        robot = _FakeRobot()
        motion = _FakeMotion()
        pickup_motion = SimpleNamespace(
            servo_contact_linear_mm_s=100.0,
            servo_contact_min_z_mm=-5.0,
            servo_contact_timeout_s=1.0,
            servo_contact_poll_interval_s=0.01,
            servo_contact_preflight_read_attempts=2,
            servo_contact_read_failure_limit=3,
            servo_contact_fallback_to_planned_descend=False,
            lift_align_vel_percent=30.0,
            lift_align_acc_percent=30.0,
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
            contact_mode=PICKUP_CONTACT_MODE_SERVO_CONTACT,
            contact_waypoint_index=1,
            retract_reference_pose=[0, 0, 100, 0, 0, 0],
        )

        self.assertTrue(executor._execute_servo_contact_pickup_sequence(plan))

        self.assertEqual(motion.vacuum_on, 1)
        self.assertTrue(motion.vacuum_required)
        self.assertEqual(robot.stopped, 2)
        self.assertEqual(
            [label for label, _segments in motion.sequences],
            [
                "Pickup approach before servo contact",
                "Pickup continuation after completed servo retract",
            ],
        )
        moved_labels = [
            segment["label"]
            for _label, segments in motion.sequences
            for segment in segments
        ]
        self.assertEqual(
            moved_labels,
            ["approach", "stage"],
        )
        self.assertEqual(motion.sequences[0][1][0]["blendR"], 0.0)
        self.assertEqual(motion.sequences[1][1][-1]["blendR"], 0.0)
        self.assertEqual(robot.started[0][1]["linear_mm_s"], 100.0)
        self.assertEqual(robot.started[1][1]["linear_mm_s"], 25.0)
        self.assertEqual(robot.started[1][0][1].name, "PLUS")
        self.assertEqual(len(robot.started), 2)
        self.assertEqual(robot.ptp_moves[0][0][2], 100.0)

    def test_servo_contact_preplans_after_servo_and_executes_after_ptp_retract(self):
        robot = _FakeRobot()
        robot.support_prepared = True
        motion = _FakeMotion()
        pickup_motion = SimpleNamespace(
            servo_contact_linear_mm_s=12.0,
            servo_contact_min_z_mm=-5.0,
            servo_contact_timeout_s=1.0,
            servo_contact_poll_interval_s=0.01,
            servo_contact_preflight_read_attempts=2,
            servo_contact_read_failure_limit=3,
            lift_align_vel_percent=30.0,
            lift_align_acc_percent=30.0,
        )
        owner = SimpleNamespace(
            _robot_service=robot, _motion=motion,
            _pickup_condition=_ConditionAfterStart(), _pickup_tool=1, _pickup_user=0,
            _paint_process_config=lambda: SimpleNamespace(pickup_motion=pickup_motion),
        )
        plan = PickupPlan(
            strategy_name="test", motion_plan=object(),
            waypoints=(
                PickupWaypoint("approach", [1, 2, 100, 0, 0, 3], 10, 10, "ptp", 0),
                PickupWaypoint("contact", [1, 2, 0, 0, 0, 3], 10, 10, "linear", 0),
                PickupWaypoint("lift", [1, 2, 50, 0, 0, 3], 10, 10, "ptp", 0),
                PickupWaypoint("stage", [10, 2, 50, 0, 0, 3], 10, 10, "ptp", 0),
            ),
            contact_mode=PICKUP_CONTACT_MODE_SERVO_CONTACT,
            contact_waypoint_index=1,
            retract_reference_pose=[9, 9, 100, 0, 0, 0],
        )

        self.assertTrue(PaintPickupExecutor(owner)._execute_servo_contact_pickup_sequence(plan))
        self.assertEqual(robot.prepared[0][1], [1, 2, 100.0, 0, 0, 3])
        self.assertEqual([segment["label"] for segment in robot.prepared[0][0]], ["stage"])
        self.assertEqual(robot.ptp_moves[0][0], [1, 2, 100.0, 0, 0, 3])
        self.assertEqual(robot.executed_prepared, ["prepared-1"])
        self.assertEqual(
            [label for label, _ in motion.sequences],
            ["Pickup approach before servo contact"],
        )

    def test_servo_contact_discards_preplan_when_ptp_retract_fails(self):
        robot = _FakeRobot()
        robot.support_prepared = True
        robot.ptp_return = False
        motion = _FakeMotion()
        pickup_motion = SimpleNamespace(
            servo_contact_linear_mm_s=12.0,
            servo_contact_min_z_mm=-5.0,
            servo_contact_timeout_s=1.0,
            servo_contact_poll_interval_s=0.01,
            servo_contact_preflight_read_attempts=2,
            servo_contact_read_failure_limit=3,
            lift_align_vel_percent=30.0,
            lift_align_acc_percent=30.0,
        )
        owner = SimpleNamespace(
            _robot_service=robot, _motion=motion,
            _pickup_condition=_ConditionAfterStart(), _pickup_tool=1, _pickup_user=0,
            _paint_process_config=lambda: SimpleNamespace(pickup_motion=pickup_motion),
        )
        plan = PickupPlan(
            strategy_name="test", motion_plan=object(),
            waypoints=(
                PickupWaypoint("approach", [1, 2, 100, 0, 0, 3], 10, 10, "ptp", 0),
                PickupWaypoint("contact", [1, 2, 0, 0, 0, 3], 10, 10, "linear", 0),
                PickupWaypoint("lift", [1, 2, 50, 0, 0, 3], 10, 10, "ptp", 0),
                PickupWaypoint("stage", [10, 2, 50, 0, 0, 3], 10, 10, "ptp", 0),
            ),
            contact_mode=PICKUP_CONTACT_MODE_SERVO_CONTACT,
            contact_waypoint_index=1,
            retract_reference_pose=[9, 9, 100, 0, 0, 0],
        )

        self.assertFalse(PaintPickupExecutor(owner)._execute_servo_contact_pickup_sequence(plan))
        self.assertEqual(robot.discarded_prepared, ["prepared-1"])
        self.assertEqual(robot.executed_prepared, [])

    def test_servo_contact_does_not_move_when_vacuum_on_fails(self):
        robot = _FakeRobot()
        motion = _FakeMotion()
        motion.turn_vacuum_on = lambda *, required=False: (False, "pump failed")
        pickup_motion = SimpleNamespace(
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
        plan = PickupPlan(
            strategy_name="test",
            motion_plan=object(),
            waypoints=(
                PickupWaypoint("approach", [0, 0, 100, 0, 0, 0], 10, 10),
                PickupWaypoint("contact", [0, 0, 0, 0, 0, 0], 10, 10),
            ),
            vacuum_on_before_moves=True,
            contact_mode=PICKUP_CONTACT_MODE_SERVO_CONTACT,
            contact_waypoint_index=1,
        )

        self.assertFalse(PaintPickupExecutor(owner)._execute_servo_contact_pickup_sequence(plan))
        self.assertEqual([], motion.sequences)
        self.assertEqual([], robot.started)

    def test_single_segment_pickup_chain_forces_terminal_blend_zero(self):
        segments = build_paint_pickup_segments([
            PickupWaypoint("approach", [0, 0, 100, 0, 0, 0], 10, 10, "ptp", 20.0),
        ])

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["blendR"], 0.0)

    def test_pickup_chain_removes_redundant_alignment_pose(self):
        pose = [10, 20, 30, 180, 0, 45]
        segments = build_paint_pickup_segments([
            PickupWaypoint("lift", pose, 10, 10, "ptp", 20.0),
            PickupWaypoint("Aligning workpiece to paint axis", list(pose), 10, 10, "ptp", 12.0),
            PickupWaypoint("stage", [20, 20, 30, 180, 0, 45], 10, 10, "ptp", 0.0),
        ])

        self.assertEqual([segment["label"] for segment in segments], ["lift", "stage"])
        self.assertEqual(segments[0]["blendR"], 12.0)

    def test_height_measure_pickup_mode_fails_fast_until_wired(self):
        robot = _FakeRobot()
        motion = _FakeMotion()
        owner = SimpleNamespace(
            _robot_service=robot,
            _motion=motion,
            _last_pickup_plan=None,
        )
        executor = PaintPickupExecutor(owner)
        executor.build_plan = lambda _prepared: PickupPlan(
            strategy_name="test",
            motion_plan=object(),
            waypoints=(
                PickupWaypoint("approach", [0, 0, 100, 0, 0, 0], 10, 10, "ptp", 0),
                PickupWaypoint("planned descend", [0, 0, 0, 0, 0, 0], 10, 10, "linear", 0),
            ),
            contact_mode=PICKUP_CONTACT_MODE_HEIGHT_MEASURE,
            contact_waypoint_index=1,
        )

        ok, msg = executor.execute(object())

        self.assertFalse(ok)
        self.assertEqual(msg, "Height-measured pickup Z mode is not wired yet")
        self.assertEqual(motion.sequences, [])
        self.assertEqual(robot.started, [])

    def test_single_segment_magazine_chain_forces_terminal_blend_zero(self):
        segments = build_magazine_pickup_release_segments((
            ("Moving to magazine pickup approach pose", [0, 0, 100, 0, 0, 0], 10, 10, "ptp", 20.0),
        ))

        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0]["blendR"], 0.0)


if __name__ == "__main__":
    unittest.main()
