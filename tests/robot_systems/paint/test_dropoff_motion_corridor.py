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
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    execute_dropoff_release_for_executor,
)


class TestDropoffMotionCorridor(unittest.TestCase):
    def test_sub_zero_release_executes_prepared_retract_and_next_cycle_start_tail(self):
        dropoff = SimpleNamespace(
            strategy="movement_group",
            allow_sub_zero_dropoff=True,
            sub_zero_approach_z_mm=50.0,
            release_align_vel_percent=20.0,
            release_align_acc_percent=15.0,
            release_align_motion_type="ptp",
            release_align_blendR=0.0,
        )
        robot = MagicMock()
        robot.prepare_ordered_motion_chain.return_value = {"plan_id": "next-cycle-1"}
        robot.execute_prepared_ordered_motion_chain.return_value = {
            "state": "completed", "result": 0,
        }
        motion = MagicMock()
        motion.move_pickup_phase.return_value = True
        motion.turn_vacuum_off.return_value = (True, "")
        owner = SimpleNamespace(
            _dropoff_motion_corridor_id="workpiece_drop_opening",
            _dropoff_unwind_prepared=False,
            _last_process_end_pose=None,
            _last_prepositioned_start_group=None,
            _robot_service=robot,
            _pickup_tool=1,
            _pickup_user=2,
            _motion=motion,
            _vacuum_sensor=None,
            _enable_vacuum_pump=False,
            _paint_process_config=lambda: SimpleNamespace(dropoff=dropoff),
        )
        next_start = {
            "group_id": "Magazine Fixed Pickup",
            "position": [-147.0, 52.0, 110.0, -179.9, 0.0, 0.0],
            "vel": 60.0,
            "acc": 40.0,
            "type": "ptp",
        }

        with patch(
            "src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers._resolve_dropoff_align_pose",
            return_value=[300.0, 120.0, -80.0, 180.0, 0.0, 0.0],
        ):
            ok, message = execute_dropoff_release_for_executor(
                owner, next_cycle_start=next_start
            )

        self.assertTrue(ok, message)
        prepared = robot.prepare_ordered_motion_chain.call_args.kwargs
        self.assertEqual(-80.0, prepared["start_position"][2])
        self.assertEqual(
            ["Retracting through dropoff group 'Dropoff' passage", "Moving to next-cycle start 'Magazine Fixed Pickup'"],
            [segment["label"] for segment in prepared["segments"]],
        )
        self.assertEqual(50.0, prepared["segments"][0]["position"][2])
        self.assertTrue(prepared["segments"][0]["protected"])
        robot.execute_prepared_ordered_motion_chain.assert_called_once_with("next-cycle-1")
        self.assertEqual("Magazine Fixed Pickup", owner._last_prepositioned_start_group)
        self.assertEqual(2, motion.move_pickup_phase.call_count)

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
            sub_zero_approach_z_mm=65.0,
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
        self.assertEqual(approach.pose[2], 65.0)
        self.assertEqual(approach.motion_type, "ptp")
        self.assertEqual(descent.pose, target)
        self.assertTrue(descent.release_here)
        self.assertEqual(descent.motion_type, "linear")
        self.assertEqual(descent.corridor_id, "workpiece_drop_opening")
        self.assertEqual(retract.pose[2], 65.0)
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

    def test_fast_lin_waypoint_calls_fast_linear_operation(self):
        robot = MagicMock()
        robot.move_fast_linear.return_value = {
            "result": 0,
            "success": True,
            "accepted": True,
            "final": True,
            "queued": False,
        }
        owner = SimpleNamespace(
            _robot_service=robot,
            _pickup_tool=1,
            _pickup_user=2,
        )

        ok = PaintMotionExecutor(owner).move_pickup_phase(
            "Fast travel",
            [300.0, 120.0, 80.0, 180.0, 0.0, 0.0],
            velocity=70.0,
            acceleration=40.0,
            motion_type="fast_lin",
        )

        self.assertTrue(ok)
        robot.move_fast_linear.assert_called_once_with(
            position=[300.0, 120.0, 80.0, 180.0, 0.0, 0.0],
            tool=1,
            user=2,
            vel=70.0,
            acc=40.0,
            trajectory_optimizer="TOTG",
        )
        robot.move_ptp.assert_not_called()
        robot.move_linear.assert_not_called()

    def test_failed_retract_fails_dropoff_before_any_next_phase_can_continue(self):
        dropoff = SimpleNamespace(
            strategy="movement_group",
            allow_sub_zero_dropoff=True,
            sub_zero_approach_z_mm=50.0,
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
