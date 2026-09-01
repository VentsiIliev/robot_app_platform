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
    _build_dropoff_release_plan,
    _execute_plate_layout_preparation,
    _plate_center_pose_with_distributed_unwind,
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
            plate_center_distributed_unwind_deg=135.0,
            plate_motion_profiles=[
                {"key": "enter_plate_center", "vel_percent": 11, "acc_percent": 21, "motion_type": "linear", "blendR": 1},
                {"key": "center_to_approach", "vel_percent": 12, "acc_percent": 22, "motion_type": "linear", "blendR": 2},
                {"key": "descend_release", "vel_percent": 13, "acc_percent": 23, "motion_type": "linear", "blendR": 3},
                {"key": "retract_after_release", "vel_percent": 14, "acc_percent": 24, "motion_type": "linear", "blendR": 4},
                {"key": "return_plate_center", "vel_percent": 15, "acc_percent": 25, "motion_type": "linear", "blendR": 5},
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
        self.assertEqual(135.0, restored.dropoff.plate_center_distributed_unwind_deg)
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

    def test_release_plan_returns_to_plate_center_after_retract(self) -> None:
        service = PlateLayoutService()
        config = PaintProcessConfig(dropoff=PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
            plate_approach_clearance_mm=40.0,
            plate_motion_profiles=[
                {"key": "enter_plate_center", "vel_percent": 11, "acc_percent": 21, "motion_type": "linear", "blendR": 1},
                {"key": "center_to_approach", "vel_percent": 12, "acc_percent": 22, "motion_type": "linear", "blendR": 2},
                {"key": "descend_release", "vel_percent": 13, "acc_percent": 23, "motion_type": "linear", "blendR": 3},
                {"key": "retract_after_release", "vel_percent": 14, "acc_percent": 24, "motion_type": "linear", "blendR": 4},
                {"key": "return_plate_center", "vel_percent": 15, "acc_percent": 25, "motion_type": "linear", "blendR": 5},
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
        executor._dropoff_motion_corridor_id = "dropoff"
        executor._contact_motion_config.rotation_index = 5

        plan = _build_dropoff_release_plan(executor)

        self.assertEqual(4, len(plan.waypoints))
        self.assertEqual("Returning through plate center", plan.waypoints[-1].label)
        self.assertEqual(service.pending.transit_pose, plan.waypoints[-1].pose)
        self.assertTrue(all(item.corridor_id == "dropoff_plate_layout" for item in plan.waypoints))
        self.assertEqual(
            [(12, 22, 2), (13, 23, 3), (14, 24, 4), (15, 25, 5)],
            [(item.vel_percent, item.acc_percent, item.blendR) for item in plan.waypoints],
        )

    def test_preparation_registers_corridor_from_fresh_not_cached_pose(self) -> None:
        service = PlateLayoutService()
        config = PaintProcessConfig(dropoff=PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
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
        executor._dropoff_motion_corridor_id = "dropoff"
        executor._robot_service.get_current_position.return_value = [999, 999, 999, 0, 0, 0]
        fresh_pose = [320, 210, 247, 180, 0, 0]
        commanded_end_pose = [175, 212, 247, 180, 0, 0]
        executor._last_process_end_pose = commanded_end_pose
        executor._robot_service.get_current_position_fresh.return_value = fresh_pose
        executor._motion.move_pickup_phase.return_value = True
        executor._robot_service.unwind_joint6.return_value = True

        ok, message = _execute_plate_layout_preparation(executor)

        self.assertTrue(ok, message)
        corridor = executor._robot_service.register_motion_corridor.call_args.args[0]
        self.assertTrue(corridor.contains_xyz(fresh_pose))
        self.assertTrue(corridor.contains_xyz(commanded_end_pose))
        self.assertTrue(corridor.contains_xyz([220, 211, 247, 180, 0, 0]))
        self.assertEqual(-110.0, corridor.x_min)
        self.assertEqual(330.0, corridor.x_max)
        executor._robot_service.get_current_position.assert_not_called()

    def test_center_lin_distributes_at_most_180_degrees_of_whole_turn_unwind(self) -> None:
        executor = MagicMock()
        executor._contact_motion_config.rotation_index = 5

        target = _plate_center_pose_with_distributed_unwind(
            executor,
            [100, 200, 250, 180, 0, 720],
            [500, -40, 100, 180, 0, 0],
            180,
        )

        self.assertEqual(540.0, target[5])

    def test_center_lin_keeps_nominal_rotation_when_no_whole_turn_is_present(self) -> None:
        executor = MagicMock()
        executor._contact_motion_config.rotation_index = 5

        target = _plate_center_pose_with_distributed_unwind(
            executor,
            [100, 200, 250, 180, 0, 170],
            [500, -40, 100, 180, 0, 0],
            180,
        )

        self.assertEqual(0.0, target[5])

    def test_failed_reservation_does_not_consume_position(self) -> None:
        service = PlateLayoutService()
        config = PaintDropoffConfig(
            strategy="plate_layout",
            plate_corners=_corners(),
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
