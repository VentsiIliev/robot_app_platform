import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.robot_systems.paint.processes.paint.execute.dropoff_executor import (
    MovementGroupDropoffStrategy,
    PaintDropoffExecutor,
)
from src.robot_systems.paint.processes.paint.execute.paint_motion_executor import (
    PaintMotionExecutor,
)


class TestDropoffMotionCorridor(unittest.TestCase):
    def test_negative_dropoff_builds_approach_descent_release_and_retract(self):
        dropoff = SimpleNamespace(
            allow_sub_zero_dropoff=True,
            release_align_vel_percent=20.0,
            release_align_acc_percent=15.0,
            release_align_motion_type="ptp",
            release_align_blendR=5.0,
        )
        owner = SimpleNamespace(
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _paint_process_config=lambda: SimpleNamespace(dropoff=dropoff),
        )
        target = [300.0, 120.0, -80.0, 180.0, 0.0, 0.0]

        with patch(
            "src.robot_systems.paint.processes.paint.execute.dropoff_executor._resolve_dropoff_align_pose",
            return_value=target,
        ):
            plan = MovementGroupDropoffStrategy().build_plan(owner, MagicMock())

        self.assertEqual(len(plan.waypoints), 3)
        approach, descent, retract = plan.waypoints
        self.assertEqual(approach.pose[2], 50.0)
        self.assertEqual(approach.motion_type, "ptp")
        self.assertEqual(descent.pose, target)
        self.assertTrue(descent.release_here)
        self.assertEqual(descent.motion_type, "linear")
        self.assertEqual(descent.corridor_id, "workpiece_drop_opening")
        self.assertEqual(retract.pose[2], 50.0)
        self.assertFalse(retract.release_here)
        self.assertEqual(retract.motion_type, "linear")
        self.assertEqual(retract.corridor_id, "workpiece_drop_opening")

    def test_negative_dropoff_is_rejected_when_setting_is_disabled(self):
        dropoff = SimpleNamespace(
            allow_sub_zero_dropoff=False,
            release_align_vel_percent=20.0,
            release_align_acc_percent=15.0,
            release_align_motion_type="ptp",
            release_align_blendR=0.0,
        )
        owner = SimpleNamespace(
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _paint_process_config=lambda: SimpleNamespace(dropoff=dropoff),
        )
        with patch(
            "src.robot_systems.paint.processes.paint.execute.dropoff_executor._resolve_dropoff_align_pose",
            return_value=[300.0, 120.0, -80.0, 180.0, 0.0, 0.0],
        ):
            plan = MovementGroupDropoffStrategy().build_plan(owner, MagicMock())

        self.assertEqual(plan.waypoints, ())

    def test_corridor_waypoint_can_only_call_corridor_linear_operation(self):
        robot = MagicMock()
        robot.move_linear_in_corridor.return_value = True
        owner = SimpleNamespace(
            _robot_service=robot,
            _pickup_tool=1,
            _pickup_user=2,
        )

        ok = PaintMotionExecutor(owner).move_pickup_phase(
            "Drop through opening",
            [300.0, 120.0, -80.0, 180.0, 0.0, 0.0],
            velocity=20.0,
            acceleration=15.0,
            motion_type="ptp",
            corridor_id="workpiece_drop_opening",
        )

        self.assertTrue(ok)
        robot.move_linear_in_corridor.assert_called_once()
        robot.move_ptp.assert_not_called()
        robot.move_linear.assert_not_called()

    def test_failed_retract_fails_dropoff_before_any_next_phase_can_continue(self):
        dropoff = SimpleNamespace(
            strategy="movement_group",
            allow_sub_zero_dropoff=True,
            release_align_vel_percent=20.0,
            release_align_acc_percent=15.0,
            release_align_motion_type="ptp",
            release_align_blendR=0.0,
        )
        motion = MagicMock()
        motion.move_pickup_phase.side_effect = [True, True, False]
        motion.turn_vacuum_off.return_value = (True, "")
        owner = SimpleNamespace(
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _dropoff_unwind_prepared=False,
            _motion=motion,
            _paint_process_config=lambda: SimpleNamespace(dropoff=dropoff),
        )
        with patch(
            "src.robot_systems.paint.processes.paint.execute.dropoff_executor._resolve_dropoff_align_pose",
            return_value=[300.0, 120.0, -80.0, 180.0, 0.0, 0.0],
        ):
            ok, message = PaintDropoffExecutor(owner).execute(MagicMock())

        self.assertFalse(ok)
        self.assertIn("Retracting", message)
        self.assertEqual(motion.move_pickup_phase.call_count, 3)
        motion.turn_vacuum_off.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
