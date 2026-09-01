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

        plan = _build_dropoff_release_plan(executor)

        self.assertEqual(4, len(plan.waypoints))
        self.assertEqual("Returning through plate center", plan.waypoints[-1].label)
        self.assertEqual(service.pending.transit_pose, plan.waypoints[-1].pose)
        self.assertTrue(all(item.corridor_id == "dropoff_plate_layout" for item in plan.waypoints))

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
        executor._robot_service.get_current_position_fresh.return_value = fresh_pose
        executor._motion.move_pickup_phase.return_value = True
        executor._robot_service.unwind_joint6.return_value = True

        ok, message = _execute_plate_layout_preparation(executor)

        self.assertTrue(ok, message)
        corridor = executor._robot_service.register_motion_corridor.call_args.args[0]
        self.assertTrue(corridor.contains_xyz(fresh_pose))
        executor._robot_service.get_current_position.assert_not_called()

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
