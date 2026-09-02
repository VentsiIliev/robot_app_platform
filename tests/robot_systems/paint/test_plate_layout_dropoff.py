import unittest
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
)
from src.robot_systems.paint.processes.paint.execution_machine.handlers.dropoff.dropoff_handlers import (
    _execute_plate_layout_preparation,
    _execute_plate_layout_ordered_release,
    _plate_route_poses_with_distributed_unwind,
)


def _corners():
    return [
        [100.0, 200.0, 10.0, 180.0, 0.0, 0.0],
        [100.0, 400.0, 10.0, 180.0, 0.0, 90.0],
        [-100.0, 400.0, 10.0, 180.0, 0.0, 180.0],
        [-100.0, 200.0, 10.0, 180.0, 0.0, -90.0],
    ]


class TestPlateLayoutDropoff(unittest.TestCase):
    def test_plate_dropoff_preparation_is_not_appended_to_pickup_paint_chain(self) -> None:
        executor = MagicMock()
        executor._paint_process_config.return_value.dropoff.strategy = "plate_layout"

        self.assertFalse(_should_preplan_dropoff_in_ordered_chain(executor))
        executor._edge_cleanup.should_run_after_xz_ry.assert_not_called()
        executor._edge_cleanup.should_run_after_xy_rz.assert_not_called()

    def test_existing_dropoff_strategy_keeps_ordered_preparation(self) -> None:
        executor = MagicMock()
        executor._paint_process_config.return_value.dropoff.strategy = "pickup_origin"
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
        self.assertEqual([1, 0.0], [item["blendR"] for item in entry])
        self.assertEqual([5, 0.0], [item["blendR"] for item in exit_chain])
        self.assertEqual(["ptp", "linear"], [item["type"] for item in entry])
        self.assertIn("passage gate to calculated dropoff", entry[-1]["label"])
        self.assertEqual(4, executor._robot_service.get_current_position_fresh.call_count)
        executor._robot_service.unwind_joint6.assert_called_once()

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

    def test_distributed_unwind_uses_four_cumulative_ninety_degree_steps(self) -> None:
        executor = MagicMock()
        executor._contact_motion_config.rotation_index = 5
        executor._robot_service.get_current_position_fresh.return_value = [0, 0, 0, 180, 0, 360]

        poses = _plate_route_poses_with_distributed_unwind(
            executor,
            gate_pose=[1, 2, 3, 180, 0, 0],
            center_pose=[4, 5, 6, 180, 0, 0],
            dropoff_pose=[7, 8, 9, 180, 0, 0],
            next_start_pose=[10, 11, 12, 180, 0, 0],
        )

        self.assertEqual(270.0, poses["entry_gate"][5])
        self.assertEqual(270.0, poses["entry_center"][5])
        self.assertEqual(180.0, poses["dropoff"][5])
        self.assertEqual(180.0, poses["exit_center"][5])
        self.assertEqual(90.0, poses["exit_gate"][5])
        self.assertEqual(0.0, poses["next_start"][5])

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


if __name__ == "__main__":
    unittest.main()
