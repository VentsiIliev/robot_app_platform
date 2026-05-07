import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
from src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts import (
    build_executed_snapshot_series,
)
from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import (
    PaintWorkpiecePathExecutor,
    _normalize_pivot_config,
)


def _execution_plan(*jobs, workpiece=None):
    return WorkpieceExecutionPlan(
        workpiece=workpiece or {},
        raw_paths=[],
        prepared_paths=[],
        curve_paths=[],
        sampled_paths=[],
        execution_jobs=list(jobs),
        total_spline_pts=0,
    )


class TestNormalizePivotConfig(unittest.TestCase):
    def test_invalid_plane_axis_and_direction_fall_back_to_defaults(self):
        config = _normalize_pivot_config(
            motion_plane="bad-plane",
            translation_axis="bad-axis",
            pivot_side="bad-side",
            translation_direction="bad-direction",
        )

        self.assertEqual("xy_z_rz", config.motion_plane)
        self.assertEqual("x", config.translation_axis)
        self.assertEqual("negative", config.paint_side)
        self.assertEqual("forward", config.translation_direction)


class TestPaintWorkpiecePathExecutor(unittest.TestCase):
    def test_prepare_workpiece_preview_builds_and_caches_execution_plan(self):
        expected_plan = _execution_plan()
        path_preparation_service = MagicMock()
        path_preparation_service.build_execution_plan.return_value = expected_plan
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            path_preparation_service=path_preparation_service,
        )

        result = executor.prepare_workpiece_preview({"workpieceId": "wp1"})

        self.assertIs(expected_plan, result)
        self.assertIs(expected_plan, executor.get_last_execution_plan())
        path_preparation_service.build_execution_plan.assert_called_once_with({"workpieceId": "wp1"})

    def test_prepare_workpiece_preview_requires_path_preparation_service(self):
        executor = PaintWorkpiecePathExecutor(robot_service=None)

        with self.assertRaises(RuntimeError):
            executor.prepare_workpiece_preview({})

    def test_get_pivot_preview_paths_skips_jobs_without_paths_and_applies_offsets(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100, 200, 300, 0, 0, 90],
        )
        execution_plan = _execution_plan(
            {"execution_path": [[0, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0]], "pivot_offset_mm": 15.0},
            {"execution_path": []},
            {"path": [[0, 0, 0, 0, 0, 0], [0, 5, 0, 0, 0, 0]], "pivot_offset_mm": -5.0},
        )

        captured_pivots = []

        def _project(path, pivot_pose, config):
            captured_pivots.append((path, list(pivot_pose), config.motion_plane))
            return [[list(pivot_pose)]], [], []

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_motion_geometry",
            side_effect=_project,
        ):
            paths, last_pivot_pose = executor.get_pivot_preview_paths(execution_plan)

        self.assertEqual(2, len(paths))
        self.assertEqual([100.0, 215.0, 300.0, 0.0, 0.0, 90.0], captured_pivots[0][1])
        self.assertEqual([100.0, 195.0, 300.0, 0.0, 0.0, 90.0], captured_pivots[1][1])
        self.assertEqual([100.0, 195.0, 300.0, 0.0, 0.0, 90.0], last_pivot_pose)

    def test_get_pivot_motion_preview_returns_projected_snapshots(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [10, 20, 30, 0, 0, 0],
        )
        execution_plan = _execution_plan(
            {"execution_path": [[0, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0]]},
        )
        expected_snapshots = [np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=float)]

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_motion_geometry",
            return_value=([], expected_snapshots, []),
        ):
            motion, last_pivot_pose = executor.get_pivot_motion_preview(execution_plan)

        self.assertEqual(1, len(motion))
        self.assertTrue(np.array_equal(expected_snapshots[0], motion[0][0]))
        self.assertEqual([10.0, 20.0, 30.0, 0.0, 0.0, 0.0], last_pivot_pose)

    def test_build_pivot_execution_path_can_rebase_start_rotation_to_zero(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [0, 0, 0, 0, 0, 0],
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_motion_geometry",
            return_value=(
                [[1, 2, 3, 0, 0, 45], [4, 5, 6, 0, 0, 60]],
                [],
                [],
            ),
        ):
            path = executor._build_pivot_execution_path(
                [[0, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0]],
                align_start_to_zero_rz=True,
            )

        self.assertEqual(0.0, path[0][5])
        self.assertEqual(15.0, path[1][5])

    def test_resolve_base_position_returns_none_for_provider_errors_or_bad_values(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: ["bad", 1, 2],
        )
        self.assertIsNone(executor._resolve_base_position())

        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [1, 2],
        )
        self.assertIsNone(executor._resolve_base_position())

        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        self.assertIsNone(executor._resolve_base_position())

    def test_apply_pivot_offset_uses_y_for_xy_mode_and_z_for_xz_mode(self):
        xy_executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [0, 0, 0, 0, 0, 0],
            pivot_motion_plane="xy_z_rz",
        )
        xz_executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [0, 0, 0, 0, 0, 0],
            pivot_motion_plane="xz_y_ry",
        )

        self.assertEqual([1.0, 7.0, 3.0], xy_executor._apply_pivot_offset([1.0, 2.0, 3.0], 5.0)[:3])
        self.assertEqual([1.0, 2.0, 8.0], xz_executor._apply_pivot_offset([1.0, 2.0, 3.0], 5.0)[:3])

    def test_build_pickup_and_stage_poses_uses_configured_pickup_offsets(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, 180.0, 5.0, 15.0],
            pivot_motion_plane="xy_z_rz",
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [11.0, 22.0],
                "pickup_rz": 33.0,
                "workpiece_height_mm": 7.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_motion_geometry",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            plan = executor._build_pickup_and_stage_poses(execution_plan)

        self.assertIsNotNone(plan)
        expected_pickup_z = 100.0 + 7.0 + PAINT_PROCESS_CONFIG.pickup_contact_offset_mm
        expected_approach_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_approach_offset_mm
        self.assertEqual(plan.pickup_pose, [11.0, 22.0, expected_pickup_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.pickup_approach_pose, [11.0, 22.0, expected_approach_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.lift_pose, plan.pickup_approach_pose)
        self.assertEqual(plan.align_pose, [11.0, 22.0, expected_approach_z, 180.0, 5.0, 44.0])
        self.assertEqual(plan.staged_pose, [101.0, 202.0, 303.0, 1.0, 2.0, 44.0])

    def test_move_pickup_phase_uses_pickup_motion_defaults(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)
        pose = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

        result = executor._move_pickup_phase("test move", pose)

        self.assertTrue(result)
        robot_service.move_ptp.assert_called_once_with(
            position=pose,
            tool=0,
            user=0,
            velocity=PAINT_PROCESS_CONFIG.pickup_default_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_default_acc_percent,
            wait_to_reach=True,
        )

    def test_build_executed_snapshot_series_rebases_preview_snapshot_to_executed_poses(self):
        pivot_config = _normalize_pivot_config(motion_plane="xy_z_rz")
        source_path = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
        executed_path = [
            [100.0, 200.0, 300.0, 0.0, 0.0, 45.0],
            [110.0, 210.0, 300.0, 0.0, 0.0, 60.0],
        ]
        pivot_pose = [50.0, 60.0, 70.0, 0.0, 0.0, 15.0]
        preview_path = [[5.0, 6.0, 0.0, 0.0, 0.0, 10.0]]
        preview_snapshots = [np.asarray([[1.0, 1.0], [3.0, 1.0]], dtype=float)]

        with patch(
            "src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts.project_paint_motion_geometry",
            return_value=(preview_path, preview_snapshots, []),
        ):
            snapshots = build_executed_snapshot_series(
                source_path=source_path,
                executed_path=executed_path,
                pivot_pose=pivot_pose,
                pivot_config=pivot_config,
            )

        self.assertEqual(2, len(snapshots))
        first_center = np.mean(snapshots[0], axis=0)
        second_center = np.mean(snapshots[1], axis=0)
        np.testing.assert_allclose(first_center, np.array([100.0, 200.0]), atol=1e-6)
        np.testing.assert_allclose(second_center, np.array([110.0, 210.0]), atol=1e-6)


if __name__ == "__main__":
    unittest.main()
