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
from src.robot_systems.paint.paint_robot_system import (
    PaintRobotSystem,
    _build_sub_zero_dropoff_corridor,
)
from src.robot_systems.paint.processes.paint.config import PaintDropoffConfig
from src.robot_systems.paint.processes.paint.paint_process_config_service import (
    PaintProcessConfigService,
)
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig


class TestDropoffMotionCorridor(unittest.TestCase):
    def test_saved_settings_update_snapshot_and_notify_live_corridor_consumer(self):
        settings_repository = MagicMock()
        initial = PaintProcessConfig()
        settings_repository.get.return_value = initial
        service = PaintProcessConfigService(settings_repository)
        listener = MagicMock()
        service.add_change_listener(listener)
        updated = PaintProcessConfig(
            dropoff=PaintDropoffConfig(corridor_z_tolerance_mm=2.5)
        )

        service.save(updated)

        self.assertIs(service.get_snapshot(), updated)
        listener.assert_called_once_with(updated)

    def test_live_refresh_replaces_registered_corridor(self):
        owner = SimpleNamespace(
            _navigation=SimpleNamespace(
                get_group_position=lambda _group: [300.0, 120.0, -100.0, 0.0, 0.0, 0.0]
            ),
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _robot=MagicMock(),
        )
        initial = PaintProcessConfig(
            dropoff=PaintDropoffConfig(corridor_z_tolerance_mm=1.0)
        )
        updated = PaintProcessConfig(
            dropoff=PaintDropoffConfig(corridor_z_tolerance_mm=3.0)
        )

        PaintRobotSystem._refresh_dropoff_motion_corridor(owner, initial)
        PaintRobotSystem._refresh_dropoff_motion_corridor(owner, updated)

        calls = owner._robot.register_motion_corridor.call_args_list
        self.assertEqual(calls[0].args[0].z_min, -101.0)
        self.assertEqual(calls[1].args[0].z_min, -103.0)

    def test_corridor_minimum_z_follows_dropoff_pose_and_tolerance(self):
        config = PaintDropoffConfig(
            corridor_x_margin_mm=25.0,
            corridor_y_margin_mm=35.0,
            corridor_z_tolerance_mm=1.0,
            corridor_entry_z_max_mm=90.0,
            corridor_maximum_velocity_percent=40.0,
            corridor_maximum_acceleration_percent=30.0,
        )

        corridor = _build_sub_zero_dropoff_corridor(
            "workpiece_drop_opening", [300.0, 120.0, -100.0, 0.0, 0.0, 0.0], config
        )

        self.assertEqual(corridor.x_min, 275.0)
        self.assertEqual(corridor.x_max, 325.0)
        self.assertEqual(corridor.y_min, 85.0)
        self.assertEqual(corridor.y_max, 155.0)
        self.assertEqual(corridor.z_min, -101.0)
        self.assertEqual(corridor.entry_z_max, 90.0)
        self.assertEqual(corridor.maximum_velocity, 40.0)
        self.assertEqual(corridor.maximum_acceleration, 30.0)

    def test_corridor_is_not_built_for_nonnegative_dropoff_pose(self):
        self.assertIsNone(
            _build_sub_zero_dropoff_corridor(
                "workpiece_drop_opening", [300.0, 120.0, 0.0, 0.0, 0.0, 0.0], PaintDropoffConfig()
            )
        )

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
