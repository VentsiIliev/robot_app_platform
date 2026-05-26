import unittest
from unittest.mock import MagicMock

import numpy as np

from src.engine.robot.path_preparation.geometry import (
    compute_pickup_rz_from_robot_contour,
)
from src.robot_systems.paint.processes.paint.pivot_projection import (
    _canonicalize_closed_source_path,
)
from src.robot_systems.paint.processes.paint.workpiece_path_executor import (
    PaintWorkpiecePathExecutor,
)
from src.engine.robot.path_preparation import WorkpieceExecutionPlan


class TestPaintMarkerPositioning(unittest.TestCase):
    def test_closed_contour_starts_at_top_center_point(self):
        contour = np.asarray(
            [
                [10.0, 10.0],
                [0.0, 10.0],
                [0.0, 0.0],
                [10.0, 0.0],
                [10.0, 10.0],
            ],
            dtype=float,
        )

        ordered = _canonicalize_closed_source_path(
            contour,
            pivot_xy=(100.0, 100.0),
            translation_heading=0.0,
            contact_segment_heading=180.0,
            side_sign=1.0,
        )

        self.assertEqual(ordered[0].tolist(), [5.0, 0.0])

    def test_closed_contour_starts_at_top_center_boundary_intersection(self):
        contour = np.asarray(
            [
                [10.0, 10.0],
                [0.0, 10.0],
                [3.0, 0.0],
                [10.0, 10.0],
            ],
            dtype=float,
        )

        ordered = _canonicalize_closed_source_path(
            contour,
            pivot_xy=(100.0, 100.0),
            translation_heading=0.0,
            contact_segment_heading=180.0,
            side_sign=1.0,
        )

        np.testing.assert_allclose(ordered[0], [5.0, 20.0 / 7.0])

    def test_closed_contour_starts_at_top_center_on_slightly_sampled_top_edge(self):
        contour = np.asarray(
            [
                [10.0, 10.0],
                [0.0, 10.0],
                [0.0, 0.0],
                [4.0, 0.05],
                [10.0, 0.0],
                [10.0, 10.0],
            ],
            dtype=float,
        )

        ordered = _canonicalize_closed_source_path(
            contour,
            pivot_xy=(100.0, 100.0),
            translation_heading=0.0,
            contact_segment_heading=180.0,
            side_sign=1.0,
        )

        np.testing.assert_allclose(ordered[0], [5.0, 0.05 * (5.0 / 6.0)])

    def test_marker_base_replaces_active_planar_coordinates_with_offsets(self):
        moved = []
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            pre_paint_position_provider=lambda: [-29.0, -386.0, 188.0, 90.0, 0.1, -0.2],
            pre_paint_move_callback=lambda: moved.append(True) or True,
            paint_base_marker_provider=lambda: (10.0, 20.0),
            paint_base_marker_offset_x_mm=7.0,
            paint_base_marker_offset_y_mm=8.0,
            paint_base_marker_offset_z_mm=9.0,
            enable_marker_paint_base=True,
            pivot_motion_plane="xz_y_ry",
        )

        ok, message = executor._prepare_marker_paint_base_position()

        self.assertTrue(ok, message)
        self.assertEqual(moved, [True])
        self.assertEqual(
            executor._resolve_base_position(),
            [-22.0, -378.0, 197.0, 90.0, 0.1, -0.2],
        )

    def test_pre_paint_marker_test_moves_to_computed_offset_pose(self):
        robot = MagicMock()
        robot.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot,
            base_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            pre_paint_position_provider=lambda: [-29.0, -386.0, 188.0, 90.0, 0.1, -0.2],
            pre_paint_move_callback=lambda: True,
            paint_base_marker_provider=lambda: (10.0, 20.0),
            paint_base_marker_offset_x_mm=7.0,
            paint_base_marker_offset_y_mm=8.0,
            paint_base_marker_offset_z_mm=9.0,
            enable_marker_paint_base=True,
            pivot_motion_plane="xz_y_ry",
        )

        ok, message = executor.test_pre_paint_marker_position()

        self.assertTrue(ok, message)
        robot.move_ptp.assert_called_once()
        self.assertEqual(
            robot.move_ptp.call_args.kwargs["position"],
            [-22.0, -378.0, 197.0, 90.0, 0.1, -0.2],
        )

    def test_xz_ry_reachability_preflight_is_disabled_by_default(self):
        robot = MagicMock()
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot,
            base_position_provider=lambda: [-29.778, -371.357, 288.635, 90.341, 0.115, -0.24],
            pivot_motion_plane="xz_y_ry",
        )

        ok, message = executor._validate_xz_ry_pivot_path(
            [
                [-29.778, -371.357, 288.635, 90.341, 0.115, -0.24],
                [18.722, -371.357, 287.740, 90.0, 0.115, -0.24],
                [58.504, -371.357, 272.061, 90.0, 22.025, -0.24],
            ]
        )

        self.assertTrue(ok, message)
        robot.validate_pose.assert_not_called()

    def test_horizontal_pickup_staging_moves_to_marker_offset_pose_before_staged_pose(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            pre_paint_position_provider=lambda: [-29.0, -386.0, 188.0, 90.0, 0.1, -0.2],
            pre_paint_move_callback=lambda: True,
            paint_base_marker_provider=lambda: (10.0, 20.0),
            paint_base_marker_offset_x_mm=7.0,
            paint_base_marker_offset_y_mm=8.0,
            paint_base_marker_offset_z_mm=9.0,
            enable_marker_paint_base=True,
            pivot_motion_plane="xz_y_ry",
        )
        ok, message = executor._prepare_marker_paint_base_position()
        self.assertTrue(ok, message)
        plan = WorkpieceExecutionPlan(
            workpiece={},
            raw_paths=[],
            prepared_paths=[],
            curve_paths=[],
            sampled_paths=[],
            execution_jobs=[
                {
                    "execution_path": [
                        [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
                        [10.0, 0.0, 0.0, 180.0, 0.0, 0.0],
                        [10.0, 10.0, 0.0, 180.0, 0.0, 0.0],
                    ],
                    "pickup_xy": [-15.0, -306.0],
                    "pickup_rz": 2.0,
                }
            ],
            total_spline_pts=3,
        )

        pickup_plan = executor._build_pickup_and_stage_poses(plan)

        self.assertIsNotNone(pickup_plan)
        self.assertEqual(pickup_plan.align_pose, pickup_plan.lift_pose)
        self.assertEqual(
            pickup_plan.change_plane_pose,
            [-22.0, -378.0, 197.0, 90.0, 0.1, -0.2],
        )
        self.assertEqual(
            [round(value, 3) for value in pickup_plan.staged_pose[:3]],
            [-22.0, -378.0, 197.0],
        )
        self.assertEqual(
            [round(value, 3) for value in pickup_plan.staged_pose[3:6]],
            [90.0, 0.1, -0.2],
        )

    def test_horizontal_full_paint_parks_at_pre_paint_pose_before_path_execution(self):
        events = []
        robot = MagicMock()
        robot.move_ptp.side_effect = lambda **kwargs: events.append(
            ("move", [round(float(value), 3) for value in kwargs["position"][:6]])
        ) or True
        robot.execute_trajectory.side_effect = lambda path, **kwargs: events.append(
            ("execute", [round(float(value), 3) for value in path[0][:6]])
        ) or 0

        executor = PaintWorkpiecePathExecutor(
            robot_service=robot,
            base_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            pre_paint_position_provider=lambda: [-29.0, -386.0, 188.0, 90.0, 0.1, -0.2],
            pre_paint_move_callback=lambda: True,
            paint_base_marker_provider=lambda: (10.0, 20.0),
            paint_base_marker_offset_x_mm=7.0,
            paint_base_marker_offset_y_mm=8.0,
            paint_base_marker_offset_z_mm=9.0,
            enable_marker_paint_base=True,
            pivot_motion_plane="xz_y_ry",
        )
        executor._write_pivot_debug_dump = lambda **kwargs: None
        executor._write_pivot_debug_plot = lambda **kwargs: None
        plan = WorkpieceExecutionPlan(
            workpiece={},
            raw_paths=[],
            prepared_paths=[],
            curve_paths=[],
            sampled_paths=[],
            execution_jobs=[
                {
                    "execution_path": [
                        [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
                        [10.0, 0.0, 0.0, 180.0, 0.0, 0.0],
                        [10.0, 10.0, 0.0, 180.0, 0.0, 0.0],
                    ],
                    "pickup_xy": [-15.0, -306.0],
                    "pickup_rz": 2.0,
                }
            ],
            total_spline_pts=3,
        )

        ok, message = executor.execute_pickup_and_paint(plan)

        self.assertTrue(ok, message)
        execute_index = next(index for index, event in enumerate(events) if event[0] == "execute")
        self.assertEqual(events[execute_index - 1], ("move", [-29.0, -386.0, 188.0, 90.0, 0.1, -0.2]))
        self.assertEqual(events[execute_index], ("execute", [-22.0, -378.0, 197.0, 90.0, 0.1, -0.2]))
        self.assertNotIn(("move", [-22.0, -378.0, 197.0, 90.0, 0.1, -0.2]), events[:execute_index])

    def test_horizontal_pivot_execution_path_starts_at_marker_offset_pose(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            pre_paint_position_provider=lambda: [-29.0, -386.0, 188.0, 90.0, 0.1, -0.2],
            pre_paint_move_callback=lambda: True,
            paint_base_marker_provider=lambda: (10.0, 20.0),
            paint_base_marker_offset_x_mm=7.0,
            paint_base_marker_offset_y_mm=8.0,
            paint_base_marker_offset_z_mm=9.0,
            enable_marker_paint_base=True,
            pivot_motion_plane="xz_y_ry",
        )
        ok, message = executor._prepare_marker_paint_base_position()
        self.assertTrue(ok, message)

        pivot_path = executor._build_pivot_execution_path(
            [
                [0.0, 0.0, 0.0, 180.0, 0.0, 0.0],
                [10.0, 0.0, 0.0, 180.0, 0.0, 0.0],
                [10.0, 10.0, 0.0, 180.0, 0.0, 0.0],
            ],
            pivot_offset_mm=0.0,
        )

        self.assertIsNotNone(pivot_path)
        self.assertEqual(
            [round(value, 3) for value in pivot_path[0][:3]],
            [-22.0, -378.0, 197.0],
        )
        self.assertEqual(
            [round(value, 3) for value in pivot_path[0][3:6]],
            [90.0, 0.1, -0.2],
        )
        self.assertLess(
            abs(float(pivot_path[1][4]) - float(pivot_path[0][4])),
            90.0,
        )

    def test_horizontal_rotation_compensation_is_applied_before_marker_anchor(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [-29.778, -371.357, 288.635, 90.341, 0.115, -0.24],
            pivot_motion_plane="xz_y_ry",
            flip_xz_ry_execution_rotation_direction=True,
        )

        pivot_path = executor._build_pivot_execution_path(
            [
                [-79.086, -366.434, 0.0, 180.0, 0.0, 0.0],
                [-17.515, -363.021, 0.0, 180.0, 0.0, 0.0],
                [33.663, -359.045, 0.0, 180.0, 0.0, 0.0],
                [32.862, -335.355, 0.0, 180.0, 0.0, 0.0],
                [29.840, -279.333, 0.0, 180.0, 0.0, 0.0],
                [15.044, -279.968, 0.0, 180.0, 0.0, 0.0],
                [-43.797, -283.787, 0.0, 180.0, 0.0, 0.0],
                [-83.461, -287.123, 0.0, 180.0, 0.0, 0.0],
                [-83.534, -302.298, 0.0, 180.0, 0.0, 0.0],
                [-80.710, -355.646, 0.0, 180.0, 0.0, 0.0],
                [-79.086, -366.434, 0.0, 180.0, 0.0, 0.0],
            ]
        )

        self.assertIsNotNone(pivot_path)
        self.assertEqual(
            [round(value, 3) for value in pivot_path[0][:6]],
            [-29.778, -371.357, 288.635, 90.341, 0.115, -0.24],
        )
        self.assertLess(
            abs(float(pivot_path[1][4]) - float(pivot_path[0][4])),
            5.0,
        )

    def test_pickup_rz_prefers_min_area_long_axis_over_pca_bias(self):
        contour = np.asarray(
            [
                [0.0, 0.0],
                [100.0, 0.0],
                [100.0, 40.0],
                [70.0, 40.0],
                [70.0, 60.0],
                [60.0, 60.0],
                [60.0, 40.0],
                [0.0, 40.0],
                [0.0, 0.0],
            ],
            dtype=float,
        )
        angle_deg = 3.0
        radians = np.radians(angle_deg)
        rotation = np.asarray(
            [
                [np.cos(radians), -np.sin(radians)],
                [np.sin(radians), np.cos(radians)],
            ],
            dtype=float,
        )
        rotated_contour = contour @ rotation.T

        self.assertAlmostEqual(
            compute_pickup_rz_from_robot_contour(rotated_contour),
            angle_deg,
            places=3,
        )


if __name__ == "__main__":
    unittest.main()
