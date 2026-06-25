import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.geometry.planar import axis_equivalent_shift_degrees
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import PAINT_PROCESS_CONFIG
from src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts import (
    build_executed_snapshot_series,
)
from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import (
    PaintWorkpiecePathExecutor,
    PickupToPivotPlan,
    _normalize_pivot_config,
    _shift_path_rotation,
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


class TestPaintPathRotationHelpers(unittest.TestCase):
    def test_axis_equivalent_shift_preserves_path_relative_rotation(self):
        shift = axis_equivalent_shift_degrees(17.834, -161.278)
        shifted = _shift_path_rotation(
            [
                [0.0, 0.0, 0.0, 0.0, 0.0, -161.278],
                [1.0, 0.0, 0.0, 0.0, 0.0, -110.736],
            ],
            rotation_index=5,
            shift_degrees=shift,
        )

        self.assertAlmostEqual(180.0, shift, places=3)
        self.assertAlmostEqual(18.722, shifted[0][5], places=3)
        self.assertAlmostEqual(69.264, shifted[1][5], places=3)


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

        def _project(path, pivot_pose, config, **_kwargs):
            captured_pivots.append((path, list(pivot_pose), config.motion_plane))
            return [[list(pivot_pose)]], [], []

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            plan = executor._build_pickup_and_stage_poses(execution_plan)

        self.assertIsNotNone(plan)
        expected_pickup_z = 100.0 + 7.0 + PAINT_PROCESS_CONFIG.pickup_contact_offset_mm
        expected_approach_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_approach_offset_mm
        expected_lift_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_initial_lift_clearance_mm
        self.assertEqual(plan.pickup_pose, [11.0, 22.0, expected_pickup_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.pickup_approach_pose, [11.0, 22.0, expected_approach_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.lift_pose, [11.0, 22.0, expected_lift_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.align_pose, [11.0, 22.0, expected_approach_z, 180.0, 5.0, 15.0])
        self.assertEqual(plan.staged_pose, [101.0, 202.0, 303.0, 1.0, 2.0, 15.0])

    def test_build_pickup_and_stage_poses_does_not_double_apply_tcp_offset_for_resolved_pickup_target(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, 180.0, 5.0, 15.0],
            pivot_motion_plane="xy_z_rz",
            apply_camera_to_tcp_for_pickup=True,
            camera_to_tcp_x_offset=50.0,
            camera_to_tcp_y_offset=25.0,
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [11.0, 22.0],
                "pickup_rz": 33.0,
                "pickup_target_point_name": "tool",
                "workpiece_height_mm": 0.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            plan = executor._build_pickup_and_stage_poses(execution_plan)

        self.assertIsNotNone(plan)
        self.assertEqual(11.0, plan.pickup_pose[0])
        self.assertEqual(22.0, plan.pickup_pose[1])
        self.assertEqual(11.0, plan.pickup_approach_pose[0])
        self.assertEqual(22.0, plan.pickup_approach_pose[1])

    def test_build_pickup_and_stage_poses_trusts_prepared_pickup_rz(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, 180.0, 5.0, 0.0],
            pivot_motion_plane="xy_z_rz",
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [11.0, 22.0],
                "pickup_rz": -6.151,
                "workpiece_height_mm": 0.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, -163.155]], [], []),
        ):
            plan = executor._build_pickup_and_stage_poses(execution_plan)

        self.assertIsNotNone(plan)
        self.assertAlmostEqual(-6.151, plan.pickup_pose[5], places=3)
        self.assertAlmostEqual(-6.151, plan.lift_pose[5], places=3)
        self.assertAlmostEqual(0.0, plan.align_pose[5], places=3)
        self.assertAlmostEqual(0.0, plan.staged_pose[5], places=3)
        self.assertAlmostEqual(6.151, plan.source_rotation_deg, places=3)

    def test_build_pickup_and_stage_poses_reprojects_after_pickup_alignment(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, 180.0, 5.0, 0.0],
            pivot_motion_plane="xy_z_rz",
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [11.0, 22.0],
                "pickup_rz": 10.0,
                "workpiece_height_mm": 0.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            side_effect=[
                ([[101.0, 202.0, 303.0, 1.0, 2.0, 10.0]], [], []),
                ([[111.0, 212.0, 313.0, 1.0, 2.0, 10.0]], [], []),
            ],
        ) as projection:
            plan = executor._build_pickup_and_stage_poses(execution_plan)

        self.assertIsNotNone(plan)
        self.assertAlmostEqual(-10.0, plan.source_rotation_deg, places=6)
        self.assertEqual([111.0, 212.0, 313.0], plan.staged_pose[:3])
        self.assertAlmostEqual(-10.0, projection.call_args_list[1].kwargs["source_rotation_deg"], places=6)

    def test_execute_pivot_paths_uses_carried_source_rotation(self):
        robot_service = MagicMock()
        robot_service.execute_trajectory.return_value = 0
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pivot_motion_plane="xy_z_rz",
            debug_dump_dir=None,
        )
        executor._last_pickup_plan = PickupToPivotPlan(
            pickup_approach_pose=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            pickup_pose=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            lift_pose=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            align_pose=[0.0, 0.0, 0.0, 0.0, 0.0, 12.0],
            stage_transition_poses=[],
            staged_pose=[101.0, 202.0, 303.0, 1.0, 2.0, 12.0],
            change_plane_pose=[0.0, 0.0, 0.0, 0.0, 0.0, 12.0],
            paint_pivot_pose=[100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            source_rotation_deg=12.0,
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [0.0, 0.0],
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            return_value=(
                [[101.0, 202.0, 303.0, 1.0, 2.0, 12.0], [111.0, 202.0, 303.0, 1.0, 2.0, 12.0]],
                [],
                [],
            ),
        ) as projection:
            ok, message, total_waypoints = executor._execute_pivot_paths(execution_plan)

        self.assertTrue(ok, message)
        self.assertEqual(2, total_waypoints)
        self.assertGreaterEqual(len(projection.call_args_list), 1)
        self.assertAlmostEqual(12.0, projection.call_args_list[0].kwargs["source_rotation_deg"], places=6)

    def test_pivot_preview_paths_use_pickup_source_rotation_and_command_mapping(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, -91.478, -0.047, -0.05],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, -178.885, -0.002, 7.393],
            pivot_motion_plane="xz_y_ry",
            mirror_xz_ry_pickup_handoff=True,
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [-6.327, 303.338],
                "pickup_rz": 7.393,
                "pickup_reference_rz": -0.05,
                "workpiece_height_mm": 0.0,
            }
        )

        def _project(_path, _pivot_pose, _config, **kwargs):
            source_rotation = float(kwargs.get("source_rotation_deg", 0.0))
            if abs(source_rotation) > 1e-9:
                return ([[-83.655, 316.814, 283.401, -91.478, -69.416, -0.05]], [], [])
            return ([[-83.655, 316.814, 283.401, -91.478, 25.0, -0.05]], [], [])

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            side_effect=_project,
        ) as projection:
            paths, _ = executor.get_pivot_preview_paths(execution_plan)

        self.assertEqual(1, len(paths))
        self.assertAlmostEqual(-0.002, paths[0][0][4], places=3)
        self.assertTrue(
            any(abs(float(call.kwargs.get("source_rotation_deg", 0.0))) > 1e-9 for call in projection.call_args_list)
        )

    def test_xz_ry_pickup_handoff_keeps_fixed_paint_rz_without_initial_pivot_rotation(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, -91.478, -0.047, -0.05],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, -178.885, -0.002, 7.393],
            pivot_motion_plane="xz_y_ry",
            mirror_xz_ry_pickup_handoff=True,
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [-6.327, 303.338],
                "pickup_rz": 7.393,
                "pickup_reference_rz": -0.05,
                "workpiece_height_mm": 0.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor._project_paint_motion_geometry_continuous",
            return_value=([[-83.655, 316.814, 283.401, -91.478, -69.416, -0.05]], [], []),
        ):
            plan = executor._build_pickup_and_stage_poses(execution_plan)

        self.assertIsNotNone(plan)
        self.assertAlmostEqual(-0.05, plan.align_pose[5], places=3)
        self.assertAlmostEqual(-0.05, plan.change_plane_pose[5], places=3)
        self.assertEqual([], plan.stage_transition_poses)
        self.assertAlmostEqual(-0.05, plan.staged_pose[5], places=3)
        self.assertAlmostEqual(-0.002, plan.staged_pose[4], places=3)

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

    def test_execute_pickup_to_pivot_uses_phase_specific_motion_settings(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            enable_vacuum_pump=False,
            pivot_motion_plane="xy_z_rz",
        )
        plan = PickupToPivotPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, 5.0],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 15.0],
            stage_transition_poses=[[10.0, 20.0, 110.0, 90.0, 0.0, 15.0]],
            staged_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
            change_plane_pose=[10.0, 20.0, 100.0, 90.0, 0.0, 15.0],
            paint_pivot_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
        )
        executor._build_pickup_and_stage_poses = MagicMock(return_value=plan)

        ok, message = executor.execute_pickup_to_pivot(_execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]}))

        self.assertTrue(ok, message)
        commanded_motion = [
            (call.kwargs["velocity"], call.kwargs["acceleration"])
            for call in robot_service.move_ptp.call_args_list
        ]
        self.assertEqual(
            [
                (PAINT_PROCESS_CONFIG.pickup_approach_vel_percent, PAINT_PROCESS_CONFIG.pickup_approach_acc_percent),
                (PAINT_PROCESS_CONFIG.pickup_descend_vel_percent, PAINT_PROCESS_CONFIG.pickup_descend_acc_percent),
                (PAINT_PROCESS_CONFIG.pickup_lift_align_vel_percent, PAINT_PROCESS_CONFIG.pickup_lift_align_acc_percent),
                (PAINT_PROCESS_CONFIG.pickup_change_plane_vel_percent, PAINT_PROCESS_CONFIG.pickup_change_plane_acc_percent),
                (
                    PAINT_PROCESS_CONFIG.pickup_stage_transition_vel_percent,
                    PAINT_PROCESS_CONFIG.pickup_stage_transition_acc_percent,
                ),
                (PAINT_PROCESS_CONFIG.pickup_first_contact_vel_percent, PAINT_PROCESS_CONFIG.pickup_first_contact_acc_percent),
            ],
            commanded_motion,
        )

    def test_execute_pickup_to_pivot_uses_deterministic_optimized_move_sequence(self):
        robot_service = MagicMock()
        robot_service.get_current_position.return_value = [0.0, 0.0, 300.0, 1.0, 2.0, 3.0]
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            enable_vacuum_pump=False,
            pivot_motion_plane="xy_z_rz",
        )
        plan = PickupToPivotPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, 5.0],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 15.0],
            stage_transition_poses=[[10.0, 20.0, 110.0, 90.0, 0.0, 15.0]],
            staged_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
            change_plane_pose=[10.0, 20.0, 100.0, 90.0, 0.0, 15.0],
            paint_pivot_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
        )
        executor._build_pickup_and_stage_poses = MagicMock(return_value=plan)

        ok, message = executor.execute_pickup_to_pivot(_execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]}))

        self.assertTrue(ok, message)
        commanded_positions = [call.kwargs["position"] for call in robot_service.move_ptp.call_args_list]
        self.assertEqual(
            [
                [10.0, 20.0, 300.0, 1.0, 2.0, 3.0],
                [10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
                [10.0, 20.0, 50.0, 180.0, 0.0, 5.0],
                [10.0, 20.0, 100.0, 180.0, 0.0, 15.0],
                [10.0, 20.0, 100.0, 90.0, 0.0, 15.0],
                [10.0, 20.0, 110.0, 90.0, 0.0, 15.0],
                [30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
            ],
            commanded_positions,
        )

    def test_pickup_stage_lifts_with_pickup_rz_before_aligning_to_reference_rz(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            enable_vacuum_pump=False,
            pivot_motion_plane="xy_z_rz",
        )
        plan = PickupToPivotPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 10.0],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, 10.0],
            lift_pose=[10.0, 20.0, 70.0, 180.0, 0.0, 10.0],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 0.0],
            stage_transition_poses=[],
            staged_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 0.0],
            change_plane_pose=[10.0, 20.0, 100.0, 90.0, 0.0, 0.0],
            paint_pivot_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 0.0],
        )
        executor._build_pickup_and_stage_poses = MagicMock(return_value=plan)

        ok, message = executor._execute_pickup_to_pivot_stage(
            _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})
        )

        self.assertTrue(ok, message)
        commanded_positions = [call.kwargs["position"] for call in robot_service.move_ptp.call_args_list]
        self.assertEqual(10.0, commanded_positions[0][5])
        self.assertEqual(10.0, commanded_positions[1][5])
        self.assertEqual(10.0, commanded_positions[2][5])
        self.assertEqual(0.0, commanded_positions[3][5])
        self.assertEqual(70.0, commanded_positions[2][2])
        self.assertEqual(100.0, commanded_positions[3][2])

    def test_pre_release_dropoff_does_not_restore_pickup_rz_before_release(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)
        executor._last_pickup_plan = PickupToPivotPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, 5.0],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 15.0],
            stage_transition_poses=[],
            staged_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
            change_plane_pose=[10.0, 20.0, 100.0, 90.0, 0.0, 15.0],
            paint_pivot_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
        )

        ok, message = executor._run_pre_release_dropoff()

        self.assertTrue(ok, message)
        commanded_positions = [call.kwargs["position"] for call in robot_service.move_ptp.call_args_list]
        self.assertEqual([[10.0, 20.0, 100.0, 180.0, 0.0, 15.0]], commanded_positions)

    def test_execute_pickup_and_paint_runs_post_execute_return_after_success(self):
        post_execute_callback = MagicMock(return_value=True)
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=post_execute_callback,
        )
        executor.execute_pickup_to_pivot = MagicMock(return_value=(True, "pickup ok"))
        executor._execute_pivot_paths = MagicMock(return_value=(True, "", 3))
        executor._run_pre_release_dropoff = MagicMock(return_value=(True, ""))
        executor._turn_vacuum_off = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_pickup_and_paint(plan)

        self.assertTrue(ok)
        self.assertIn("3 waypoints", msg)
        post_execute_callback.assert_called_once_with()

    def test_execute_pickup_and_paint_fails_when_post_execute_return_fails(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=False),
        )
        executor.execute_pickup_to_pivot = MagicMock(return_value=(True, "pickup ok"))
        executor._execute_pivot_paths = MagicMock(return_value=(True, "", 3))
        executor._run_pre_release_dropoff = MagicMock(return_value=(True, ""))
        executor._turn_vacuum_off = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_pickup_and_paint(plan)

        self.assertFalse(ok)
        self.assertEqual("Pickup and pivot paint finished, but return-to-calibration failed", msg)

    def test_execute_pickup_and_paint_returns_to_calibration_after_pivot_failure(self):
        post_execute_callback = MagicMock(return_value=True)
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=post_execute_callback,
        )
        executor.execute_pickup_to_pivot = MagicMock(return_value=(True, "pickup ok"))
        executor._execute_pivot_paths = MagicMock(return_value=(False, "pivot failed", 0))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_pickup_and_paint(plan)

        self.assertFalse(ok)
        self.assertEqual("pivot failed", msg)
        post_execute_callback.assert_called_once_with()

    def test_execute_pickup_and_paint_reports_cleanup_failure_after_motion_failure(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=False),
        )
        executor.execute_pickup_to_pivot = MagicMock(return_value=(True, "pickup ok"))
        executor._execute_pivot_paths = MagicMock(return_value=(True, "", 3))
        executor._run_pre_release_dropoff = MagicMock(return_value=(False, "restore failed"))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_pickup_and_paint(plan)

        self.assertFalse(ok)
        self.assertEqual("restore failed; additionally, return-to-calibration failed", msg)

    def test_build_executed_snapshot_series_rebases_preview_snapshot_to_executed_poses(self):
        pivot_config = _normalize_pivot_config(motion_plane="xy_z_rz")
        source_path = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
        executed_path = [
            [100.0, 200.0, 300.0, 0.0, 0.0, 45.0],
            [110.0, 210.0, 300.0, 0.0, 0.0, 60.0],
        ]
        pivot_pose = [50.0, 60.0, 70.0, 0.0, 0.0, 15.0]
        preview_path = [[2.0, 1.0, 0.0, 0.0, 0.0, 10.0]]
        preview_snapshots = [np.asarray([[1.0, 1.0], [3.0, 1.0]], dtype=float)]

        with patch(
            "src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts.project_paint_motion_geometry_continuous",
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

    def test_build_executed_snapshot_series_does_not_rotate_snapshots_from_command_axis_shift(self):
        pivot_config = _normalize_pivot_config(motion_plane="xy_z_rz")
        source_path = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0], [10.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
        executed_path = [[100.0, 200.0, 300.0, 0.0, 0.0, 90.0]]
        pivot_pose = [50.0, 60.0, 70.0, 0.0, 0.0, 15.0]
        preview_path = [[10.0, 20.0, 0.0, 0.0, 0.0, 10.0]]
        preview_snapshots = [np.asarray([[9.0, 20.0], [11.0, 20.0]], dtype=float)]

        with patch(
            "src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts.project_paint_motion_geometry_continuous",
            return_value=(preview_path, preview_snapshots, []),
        ):
            snapshots = build_executed_snapshot_series(
                source_path=source_path,
                executed_path=executed_path,
                pivot_pose=pivot_pose,
                pivot_config=pivot_config,
            )

        np.testing.assert_allclose(snapshots[0], np.asarray([[99.0, 200.0], [101.0, 200.0]]), atol=1e-6)


if __name__ == "__main__":
    unittest.main()
