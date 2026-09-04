import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from src.robot_systems.paint.processes.paint.config import PaintDropoffConfig
from src.robot_systems.paint.processes.paint.config import PaintProcessConfig
from src.robot_systems.paint.applications.paint_process_settings.mapper import PaintProcessSettingsMapper
from src.robot_systems.paint.processes.paint.execution_machine.handlers.magazine_load.magazine_execute_pickup_release_handler import (
    calculate_workpiece_dropoff_pose,
)
from src.robot_systems.paint.processes.paint.plate_layout import (
    PlateLayoutService,
    validate_plate_corners,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.workflow.pickup_handler import (
    _should_preplan_dropoff_in_ordered_chain,
    _paint_pass_metadata,
    _workpiece_footprint_mm,
    _workpiece_layout_geometry,
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    _execute_plate_layout_preparation,
    _execute_plate_layout_ordered_release,
    _plate_route_poses_with_distributed_unwind,
    _plate_route_uses_center,
    _wait_for_motion_slot_idle,
)


def _corners():
    return [
        [100.0, 200.0, 10.0, 180.0, 0.0, 0.0],
        [100.0, 400.0, 10.0, 180.0, 0.0, 90.0],
        [-100.0, 400.0, 10.0, 180.0, 0.0, 180.0],
        [-100.0, 200.0, 10.0, 180.0, 0.0, -90.0],
    ]


class TestPlateLayoutDropoff(unittest.TestCase):
    def test_paint_pass_metadata_records_two_distinct_pass_settings(self) -> None:
        execution_plan = MagicMock()
        execution_plan.workpiece = {"workpieceId": "captured"}
        execution_plan.execution_jobs = [{"vel": 21.0, "acc": 32.0}]
        config = PaintProcessConfig(
            unmatched_paint_pass_count=2,
            unmatched_second_pass=SimpleNamespace(
                use_pass_1_settings=False,
                velocity_percent=41.0,
                acceleration_percent=52.0,
                offset_mm=1.5,
            ),
        )
        executor = MagicMock()
        executor._resolve_pivot_offset_mm.return_value = 0.7

        passes = _paint_pass_metadata(execution_plan, config, executor)

        self.assertEqual(passes, (
            {
                "pass_number": 1,
                "velocity_percent": 21.0,
                "acceleration_percent": 32.0,
                "press_offset_mm": 0.7,
            },
            {
                "pass_number": 2,
                "velocity_percent": 41.0,
                "acceleration_percent": 52.0,
                "press_offset_mm": 1.5,
            },
        ))

    def test_committed_placement_keeps_painted_timestamp_metadata(self) -> None:
        painted_at = datetime(2026, 9, 4, 11, 30, 15, tzinfo=timezone.utc)
        service = PlateLayoutService(clock=lambda: painted_at)
        config = PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
        )
        service.reserve(
            config,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=0.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
            paint_passes=({
                "pass_number": 1,
                "velocity_percent": 20.0,
                "acceleration_percent": 30.0,
                "press_offset_mm": 0.5,
            },),
        )

        service.commit(config)

        placement = service.snapshot(config)["placements"][0]
        self.assertEqual(placement["painted_at"], painted_at.isoformat())
        self.assertEqual(placement["paint_pass_count"], 1)
        self.assertEqual(placement["paint_passes"][0]["press_offset_mm"], 0.5)

    def test_workpiece_footprint_always_uses_long_side_as_width(self) -> None:
        execution_plan = MagicMock()
        execution_plan.execution_paths.return_value = [[
            [-10.0, -30.0],
            [10.0, -30.0],
            [10.0, 30.0],
            [-10.0, 30.0],
        ]]

        width, height = _workpiece_footprint_mm(execution_plan)

        self.assertAlmostEqual(60.0, width)
        self.assertAlmostEqual(20.0, height)

    def test_workpiece_layout_geometry_preserves_normalized_outline(self) -> None:
        execution_plan = MagicMock()
        execution_plan.execution_paths.return_value = [[
            [0.0, 0.0],
            [40.0, 0.0],
            [40.0, 10.0],
            [20.0, 20.0],
            [0.0, 10.0],
        ]]

        width, height, outlines = _workpiece_layout_geometry(execution_plan)

        self.assertAlmostEqual(40.0, width)
        self.assertAlmostEqual(20.0, height)
        self.assertEqual(1, len(outlines))
        self.assertEqual(5, len(outlines[0]))
        self.assertGreater(len(set(outlines[0])), 4)

    def test_workpiece_outline_orientation_is_independent_of_contour_order(self) -> None:
        points = [
            [0.0, 0.0],
            [40.0, 0.0],
            [40.0, 10.0],
            [20.0, 20.0],
            [0.0, 10.0],
        ]
        forward_plan = MagicMock()
        forward_plan.execution_paths.return_value = [points]
        reverse_plan = MagicMock()
        reverse_plan.execution_paths.return_value = [[
            [x + 100.0, y + 50.0] for x, y in reversed(points)
        ]]

        _, _, forward_outlines = _workpiece_layout_geometry(forward_plan)
        _, _, reverse_outlines = _workpiece_layout_geometry(reverse_plan)

        normalized_forward = {
            (round(x, 4), round(y, 4)) for x, y in forward_outlines[0]
        }
        normalized_reverse = {
            (round(x, 4), round(y, 4)) for x, y in reverse_outlines[0]
        }
        self.assertEqual(normalized_forward, normalized_reverse)

    def test_automatic_center_route_is_used_inside_half_corner_to_center_radius(self) -> None:
        dropoff = SimpleNamespace(
            plate_use_center_waypoint=False,
            plate_corners=[[0.0, 0.0, 0.0, 180.0, 0.0, 0.0]],
        )
        reservation = SimpleNamespace(
            transit_pose=[100.0, 100.0, 50.0, 180.0, 0.0, 0.0],
            release_pose=[25.0, 25.0, 10.0, 180.0, 0.0, 0.0],
        )

        self.assertTrue(_plate_route_uses_center(dropoff, reservation))

    def test_automatic_center_route_is_skipped_outside_half_corner_to_center_radius(self) -> None:
        dropoff = SimpleNamespace(
            plate_use_center_waypoint=False,
            plate_corners=[[0.0, 0.0, 0.0, 180.0, 0.0, 0.0]],
        )
        reservation = SimpleNamespace(
            transit_pose=[100.0, 100.0, 50.0, 180.0, 0.0, 0.0],
            release_pose=[150.0, 150.0, 10.0, 180.0, 0.0, 0.0],
        )

        self.assertFalse(_plate_route_uses_center(dropoff, reservation))

    def test_explicit_center_route_setting_forces_center_for_far_position(self) -> None:
        dropoff = SimpleNamespace(
            plate_use_center_waypoint=True,
            plate_corners=[],
        )
        reservation = SimpleNamespace(transit_pose=[], release_pose=[])

        self.assertTrue(_plate_route_uses_center(dropoff, reservation))

    def test_plate_entry_waits_for_two_inactive_motion_status_samples(self) -> None:
        executor = MagicMock()
        executor._robot_service.get_execution_status.side_effect = [
            {"is_executing": True},
            {"is_executing": False},
            {"is_executing": False},
        ]

        self.assertTrue(_wait_for_motion_slot_idle(
            executor, timeout_s=0.1, poll_interval_s=0.005
        ))
        self.assertEqual(3, executor._robot_service.get_execution_status.call_count)

    def test_plate_dropoff_preparation_is_not_appended_to_pickup_paint_chain(self) -> None:
        executor = MagicMock()
        executor._paint_process_config.return_value.dropoff.strategy = "plate_layout"

        self.assertFalse(_should_preplan_dropoff_in_ordered_chain(executor))
        executor._edge_cleanup.should_run_after_xz_ry.assert_not_called()
        executor._edge_cleanup.should_run_after_xy_rz.assert_not_called()

    def test_existing_dropoff_strategy_keeps_ordered_preparation(self) -> None:
        executor = MagicMock()
        executor._paint_process_config.return_value.dropoff.strategy = "movement_group"
        executor._edge_cleanup.should_run_after_xz_ry.return_value = False
        executor._edge_cleanup.should_run_after_xy_rz.return_value = False

        self.assertTrue(_should_preplan_dropoff_in_ordered_chain(executor))

    def test_settings_mapper_roundtrips_plate_strategy_and_corners(self) -> None:
        config = PaintProcessConfig(dropoff=PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_approach_clearance_mm=35.0,
            plate_robot_tool=7,
            plate_robot_user=3,
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
            plate_use_center_waypoint=False,
            plate_distribute_unwind=True,
            plate_motion_profiles=[
                {"key": "entry_gate", "vel_percent": 11, "acc_percent": 21, "motion_type": "ptp", "blendR": 1},
                {"key": "entry_center", "vel_percent": 12, "acc_percent": 22, "motion_type": "ptp", "blendR": 2},
                {"key": "center_to_dropoff", "vel_percent": 13, "acc_percent": 23, "motion_type": "linear", "blendR": 3},
                {"key": "exit_center", "vel_percent": 14, "acc_percent": 24, "motion_type": "ptp", "blendR": 4},
                {"key": "exit_gate", "vel_percent": 15, "acc_percent": 25, "motion_type": "ptp", "blendR": 5},
                {"key": "gate_to_next_start", "vel_percent": 16, "acc_percent": 26, "motion_type": "ptp", "blendR": 6},
            ],
        ))

        restored = PaintProcessSettingsMapper.from_flat_dict(
            PaintProcessSettingsMapper.to_flat_dict(config),
            PaintProcessConfig(),
        )

        self.assertEqual("plate_layout", restored.dropoff.strategy)
        self.assertEqual(_corners(), restored.dropoff.plate_corners)
        self.assertEqual(35.0, restored.dropoff.plate_approach_clearance_mm)
        self.assertEqual(7, restored.dropoff.plate_robot_tool)
        self.assertEqual(3, restored.dropoff.plate_robot_user)
        self.assertEqual([200, 100, 180, 180, 0, 0], restored.dropoff.plate_passage_gate_pose)
        self.assertFalse(restored.dropoff.plate_use_center_waypoint)
        self.assertTrue(restored.dropoff.plate_distribute_unwind)
        self.assertEqual(config.dropoff.plate_motion_profiles, restored.dropoff.plate_motion_profiles)

    def test_requires_exactly_four_corners_without_fallback(self) -> None:
        corners, error = validate_plate_corners(_corners()[:3])

        self.assertEqual([], corners)
        self.assertIn("exactly four", error)

    def test_rejects_inconsistent_corner_order(self) -> None:
        corners = _corners()
        corners[1], corners[2] = corners[2], corners[1]

        _, error = validate_plate_corners(corners)

        self.assertIn("consistently ordered", error)

    def test_reserves_pose_rotated_from_calibration_into_plate_frame(self) -> None:
        service = PlateLayoutService()
        config = PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
            plate_use_center_waypoint=False,
            plate_margin_left_mm=10.0,
            plate_margin_right_mm=10.0,
            plate_margin_bottom_mm=10.0,
            plate_margin_top_mm=10.0,
            plate_spacing_x_mm=5.0,
            plate_spacing_y_mm=5.0,
            plate_approach_clearance_mm=40.0,
        )

        reservation, error = service.reserve(
            config,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=25.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
        )

        self.assertEqual("", error)
        self.assertIsNotNone(reservation)
        self.assertAlmostEqual(115.0, reservation.release_pose[5])
        self.assertAlmostEqual(reservation.release_pose[2] + 40.0, reservation.approach_pose[2])
        self.assertAlmostEqual(0.0, reservation.transit_pose[0])
        self.assertAlmostEqual(300.0, reservation.transit_pose[1])
        self.assertAlmostEqual(50.0, reservation.transit_pose[2])
        self.assertTrue(reservation.has_space_for_same_footprint)

    def test_ordered_release_uses_configured_entry_and_exit_chains(self) -> None:
        service = PlateLayoutService()
        config = PaintProcessConfig(dropoff=PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
            plate_use_center_waypoint=False,
            plate_distribute_unwind=True,
            plate_approach_clearance_mm=40.0,
            plate_motion_profiles=[
                {"key": "entry_gate", "vel_percent": 11, "acc_percent": 21, "motion_type": "ptp", "blendR": 1},
                {"key": "entry_center", "vel_percent": 12, "acc_percent": 22, "motion_type": "ptp", "blendR": 2},
                {"key": "center_to_dropoff", "vel_percent": 13, "acc_percent": 23, "motion_type": "linear", "blendR": 3},
                {"key": "exit_center", "vel_percent": 14, "acc_percent": 24, "motion_type": "ptp", "blendR": 4},
                {"key": "exit_gate", "vel_percent": 15, "acc_percent": 25, "motion_type": "ptp", "blendR": 5},
                {"key": "gate_to_next_start", "vel_percent": 16, "acc_percent": 26, "motion_type": "ptp", "blendR": 6},
            ],
        ))
        service.reserve(
            config.dropoff,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=0.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
        )
        executor = MagicMock()
        executor._paint_process_config.return_value = config
        executor._plate_layout_service = service
        executor._last_process_start_rz = 0.0
        executor._last_process_end_pose = [0, 0, 0, 180, 0, 360.0]
        executor._motion.move_ordered_pickup_sequence.return_value = True
        executor._motion.turn_vacuum_off.return_value = (True, "")
        executor._enable_vacuum_pump = False
        executor._is_vacuum_pump_enabled.return_value = False
        executor._robot_service.get_current_position_fresh.side_effect = [
            [0, 0, 0, 180, 0, 360],
            [200, 100, 180, 180, 0, 0],
            [10, 20, 30, 180, 0, 0],
            [10, 20, 30, 180, 0, 0],
        ]
        next_start = {"group_id": "Start", "position": [10, 20, 30, 180, 0, 0]}

        ok, message = _execute_plate_layout_ordered_release(executor, next_cycle_start=next_start)

        self.assertTrue(ok, message)
        entry = executor._motion.move_ordered_pickup_sequence.call_args_list[0].args[1]
        exit_chain = executor._motion.move_ordered_pickup_sequence.call_args_list[1].args[1]
        self.assertEqual([1, 2, 0.0], [item["blendR"] for item in entry])
        self.assertEqual([4, 5, 0.0], [item["blendR"] for item in exit_chain])
        self.assertEqual(["ptp", "ptp", "linear"], [item["type"] for item in entry])
        self.assertIn("center to calculated dropoff", entry[-1]["label"])
        self.assertAlmostEqual(90.0, entry[-1]["position"][5] % 360.0)
        self.assertAlmostEqual(0.0, exit_chain[-1]["position"][5] % 360.0)
        self.assertEqual(2, executor._motion.move_ordered_pickup_sequence.call_count)
        self.assertEqual("Start", executor._last_prepositioned_start_group)
        executor._robot_service.unwind_joint6.assert_not_called()

    def test_preparation_unwinds_at_detach_without_moving(self) -> None:
        service = PlateLayoutService()
        config = PaintProcessConfig(dropoff=PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
            plate_approach_clearance_mm=40.0,
        ))
        service.reserve(
            config.dropoff,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=0.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
        )
        executor = MagicMock()
        executor._paint_process_config.return_value = config
        executor._plate_layout_service = service
        executor._robot_service.unwind_joint6.return_value = True

        ok, message = _execute_plate_layout_preparation(executor)

        self.assertTrue(ok, message)
        executor._robot_service.unwind_joint6.assert_called_once()
        executor._motion.move_pickup_phase.assert_not_called()

    def test_distributed_unwind_uses_four_negative_ninety_degree_steps(self) -> None:
        executor = MagicMock()
        executor._contact_motion_config.rotation_index = 5
        executor._last_process_start_rz = 0.0
        executor._last_process_end_pose = [0, 0, 0, 180, 0, 360.0]
        executor._robot_service.get_current_position_fresh.return_value = [0, 0, 0, 180, 0, 360]

        poses = _plate_route_poses_with_distributed_unwind(
            executor,
            gate_pose=[1, 2, 3, 180, 0, 0],
            center_pose=[4, 5, 6, 180, 0, 0],
            dropoff_pose=[7, 8, 9, 180, 0, 0],
            next_start_pose=[10, 11, 12, 180, 0, 0],
            use_center_waypoint=True,
        )

        self.assertEqual(270.0, poses["entry_gate"][5])
        self.assertEqual(270.0, poses["entry_center"][5])
        self.assertEqual(180.0, poses["dropoff"][5])
        self.assertEqual(180.0, poses["exit_center"][5])
        self.assertEqual(90.0, poses["exit_gate"][5])
        self.assertEqual(0.0, poses["next_start"][5])

    def test_distributed_unwind_is_positive_when_paint_rz_rotation_is_negative(self) -> None:
        executor = MagicMock()
        executor._contact_motion_config.rotation_index = 5
        executor._last_process_start_rz = 0.0
        executor._last_process_end_pose = [0, 0, 0, 180, 0, -360.0]
        executor._robot_service.get_current_position_fresh.return_value = [0, 0, 0, 180, 0, -360]

        poses = _plate_route_poses_with_distributed_unwind(
            executor,
            gate_pose=[1, 2, 3, 180, 0, 0],
            center_pose=[4, 5, 6, 180, 0, 0],
            dropoff_pose=[7, 8, 9, 180, 0, 0],
            next_start_pose=[10, 11, 12, 180, 0, 0],
            use_center_waypoint=True,
        )

        self.assertEqual(-270.0, poses["entry_gate"][5])
        self.assertEqual(-180.0, poses["dropoff"][5])
        self.assertEqual(-90.0, poses["exit_gate"][5])
        self.assertEqual(0.0, poses["next_start"][5])

    def test_distributed_unwind_preserves_dropoff_rectangle_orientation_modulo_180(self) -> None:
        executor = MagicMock()
        executor._contact_motion_config.rotation_index = 5
        executor._last_process_start_rz = 0.0
        executor._last_process_end_pose = [0, 0, 0, 180, 0, 360.0]
        executor._robot_service.get_current_position_fresh.return_value = [0, 0, 0, 180, 0, 360]

        poses = _plate_route_poses_with_distributed_unwind(
            executor,
            gate_pose=[1, 2, 3, 180, 0, 0],
            center_pose=[4, 5, 6, 180, 0, 0],
            dropoff_pose=[7, 8, 9, 180, 0, 25],
            next_start_pose=[10, 11, 12, 180, 0, 0],
            use_center_waypoint=False,
        )

        self.assertEqual(205.0, poses["dropoff"][5])
        self.assertEqual(25.0, poses["dropoff"][5] % 180.0)
        self.assertEqual(282.5, poses["entry_gate"][5])
        self.assertEqual(102.5, poses["exit_gate"][5])

    def test_failed_reservation_does_not_consume_position(self) -> None:
        service = PlateLayoutService()
        config = PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
            plate_margin_left_mm=10.0,
            plate_margin_right_mm=10.0,
            plate_margin_bottom_mm=10.0,
            plate_margin_top_mm=10.0,
        )
        kwargs = dict(
            config=config,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=0.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
        )
        first, _ = service.reserve(**kwargs)
        service.cancel()
        second, _ = service.reserve(**kwargs)

        self.assertEqual(first.release_pose, second.release_pose)

    def test_removed_workpiece_space_is_reused(self) -> None:
        service = PlateLayoutService()
        config = PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
            plate_margin_left_mm=10.0,
            plate_margin_right_mm=10.0,
            plate_margin_bottom_mm=10.0,
            plate_margin_top_mm=10.0,
            plate_spacing_x_mm=5.0,
            plate_spacing_y_mm=5.0,
        )
        kwargs = dict(
            config=config,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=0.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
        )
        first, _ = service.reserve(**kwargs)
        service.commit(config)
        second, _ = service.reserve(**kwargs)
        service.commit(config)

        self.assertNotEqual(first.left_mm, second.left_mm)
        self.assertTrue(service.remove(first.placement_id))
        replacement, error = service.reserve(**kwargs)

        self.assertEqual("", error)
        self.assertEqual(first.left_mm, replacement.left_mm)
        self.assertEqual(first.bottom_mm, replacement.bottom_mm)

    def test_new_tray_clears_committed_and_pending_workpieces(self) -> None:
        service = PlateLayoutService()
        config = PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_passage_gate_pose=[200, 100, 180, 180, 0, 0],
        )
        kwargs = dict(
            config=config,
            width_mm=20.0,
            height_mm=30.0,
            calibration_pose=[0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
            workpiece_rz_at_calibration_deg=0.0,
            pose_calculator=calculate_workpiece_dropoff_pose,
        )
        service.reserve(**kwargs)
        service.commit(config)
        service.reserve(**kwargs)

        service.clear()
        state = service.snapshot(config)

        self.assertEqual([], state["placements"])
        self.assertIsNone(state["pending"])


if __name__ == "__main__":
    unittest.main()
