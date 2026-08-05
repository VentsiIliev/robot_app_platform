import unittest
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.geometry.planar import axis_equivalent_shift_degrees
from src.engine.robot.path_preparation import WorkpieceExecutionPlan
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintDropoffConfig,
    PaintMagazineLoadConfig,
    PaintProcessConfig,
    PaintSafeTravelConfig,
    PaintToDropoffSafeTravelConfig,
)
from src.robot_systems.paint.processes.paint.execution_control import PaintExecutionControl
from src.robot_systems.paint.processes.paint.execute.paint_debug_artifacts import (
    build_executed_snapshot_series,
)
from src.robot_systems.paint.processes.paint.execute.dropoff_executor import _poses_close
from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import (
    PaintWorkpiecePathExecutor,
    PickupTransferPlan,
    _normalize_contact_motion_config,
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
        config = _normalize_contact_motion_config(
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
    def test_prepare_workpiece_execution_plan_builds_and_caches_execution_plan(self):
        expected_plan = _execution_plan()
        path_preparation_service = MagicMock()
        path_preparation_service.build_execution_plan.return_value = expected_plan
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            path_preparation_service=path_preparation_service,
        )

        result = executor.prepare_workpiece_execution_plan({"workpieceId": "wp1"})

        self.assertIs(expected_plan, result)
        self.assertIs(expected_plan, executor.get_last_execution_plan())
        path_preparation_service.build_execution_plan.assert_called_once_with(
            {"workpieceId": "wp1"},
            skip_debug_plot=False,
        )

    def test_prepare_workpiece_execution_plan_requires_path_preparation_service(self):
        executor = PaintWorkpiecePathExecutor(robot_service=None)

        with self.assertRaises(RuntimeError):
            executor.prepare_workpiece_execution_plan({})

    def test_controlled_paint_preplans_pickup_and_contact_in_one_ordered_chain(self):
        robot_service = MagicMock()
        robot_service.execute_ordered_motion_chain.return_value = 0
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            post_execute_callback=MagicMock(return_value=True),
        )
        executor._pickup = MagicMock()
        executor._pickup.build_plan.return_value = SimpleNamespace(
            motion_plan=SimpleNamespace(),
            vacuum_on_before_moves=False,
            change_plane_combined_with_first_contact=False,
            waypoints=[
                SimpleNamespace(label="Moving to pickup approach pose", pose=[1, 2, 3, 4, 5, 6], vel_percent=11, acc_percent=21),
                SimpleNamespace(label="Moving to staging offset before first pivot contact pose", pose=[7, 8, 9, 10, 11, 12], vel_percent=12, acc_percent=22),
            ],
        )
        executor._paint_contact.execute = MagicMock(
            return_value=(True, "", 2),
        )
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._edge_cleanup.should_run_after_xy_rz = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        control = PaintExecutionControl()
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})
        command_path = [[13, 14, 15, 16, 17, 18], [19, 20, 21, 22, 23, 24]]

        def _collect_contact(_plan, **kwargs):
            kwargs["collected_command_paths"].append(command_path)
            kwargs["collected_command_jobs"].append({"pattern_type": "Path", "vel": 33, "acc": 44})
            return True, "", len(command_path)

        executor._paint_contact.execute.side_effect = _collect_contact

        ok, msg = executor.execute_paint_process(plan, control=control)

        self.assertTrue(ok, msg)
        executor._paint_contact.execute.assert_called_once()
        self.assertFalse(executor._paint_contact.execute.call_args.kwargs["execute_robot"])
        robot_service.execute_ordered_motion_chain.assert_called_once()
        segments = robot_service.execute_ordered_motion_chain.call_args.args[0]
        self.assertEqual(["linear", "linear", "path"], [segment["type"] for segment in segments])
        self.assertEqual(command_path, segments[-1]["path"])
        self.assertEqual("paint_contact_1:Path", segments[-1]["label"])
        self.assertTrue(segments[-1]["protected"])
        executor._prepare_dropoff_joint6_unwind.assert_called_once()
        executor._dropoff.execute.assert_called_once_with(plan)

    def test_controlled_paint_retries_ordered_chain_when_pause_resume_happens_before_stop_result(self):
        robot_service = MagicMock()
        robot_service.get_execution_status.return_value = {
            "ordered_motion_chain": {
                "active": True,
                "phase": "executing",
                "current_segment_index": 1,
                "current_segment_protected": False,
            }
        }
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            post_execute_callback=MagicMock(return_value=True),
        )
        executor._pickup = MagicMock()
        executor._pickup.build_plan.return_value = SimpleNamespace(
            motion_plan=SimpleNamespace(),
            vacuum_on_before_moves=False,
            change_plane_combined_with_first_contact=False,
            waypoints=[
                SimpleNamespace(label="Moving to pickup approach pose", pose=[1, 2, 3, 4, 5, 6], vel_percent=11, acc_percent=21),
                SimpleNamespace(label="Moving to staging offset before first pivot contact pose", pose=[7, 8, 9, 10, 11, 12], vel_percent=12, acc_percent=22),
            ],
        )
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._edge_cleanup.should_run_after_xy_rz = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        control = PaintExecutionControl()
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})
        command_path = [[13, 14, 15, 16, 17, 18], [19, 20, 21, 22, 23, 24]]

        def _collect_contact(_plan, **kwargs):
            kwargs["collected_command_paths"].append(command_path)
            kwargs["collected_command_jobs"].append({"pattern_type": "Path", "vel": 33, "acc": 44})
            return True, "", len(command_path)

        def _execute_chain(*_args, **_kwargs):
            if robot_service.execute_ordered_motion_chain.call_count == 1:
                control.request_pause()
                executor.pause_current_execution()
                control.resume()
                return -1
            return 0

        executor._paint_contact.execute = MagicMock(side_effect=_collect_contact)
        robot_service.execute_ordered_motion_chain.side_effect = _execute_chain

        ok, msg = executor.execute_paint_process(plan, control=control)

        self.assertTrue(ok, msg)
        self.assertEqual(2, robot_service.execute_ordered_motion_chain.call_count)
        retry_segments = robot_service.execute_ordered_motion_chain.call_args_list[1].args[0]
        self.assertEqual(["linear", "path"], [segment["type"] for segment in retry_segments])
        self.assertEqual("Moving to staging offset before first pivot contact pose", retry_segments[0]["label"])

    def test_pause_current_execution_stops_non_protected_ordered_segment(self):
        robot_service = MagicMock()
        robot_service.get_execution_status.return_value = {
            "ordered_motion_chain": {
                "active": True,
                "phase": "executing",
                "current_segment_protected": False,
            }
        }
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)

        executor.pause_current_execution()

        robot_service.stop_motion.assert_called_once_with()

    def test_pause_current_execution_defers_stop_for_protected_ordered_segment(self):
        robot_service = MagicMock()
        robot_service.get_execution_status.return_value = {
            "ordered_motion_chain": {
                "active": True,
                "phase": "executing",
                "current_segment_protected": True,
            }
        }
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)

        executor.pause_current_execution()

        robot_service.stop_motion.assert_not_called()

    def test_refresh_process_config_updates_vacuum_pump_flag(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(enable_vacuum_pump=False)
        vacuum = MagicMock()
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            vacuum_pump=vacuum,
            paint_process_config_service=config_service,
            enable_vacuum_pump=True,
        )

        executor._refresh_paint_process_config_snapshot()
        on_ok, on_msg = executor._turn_vacuum_on()
        off_ok, off_msg = executor._turn_vacuum_off()

        self.assertTrue(on_ok)
        self.assertEqual("", on_msg)
        self.assertTrue(off_ok)
        self.assertEqual("", off_msg)
        vacuum.turn_on.assert_not_called()
        vacuum.turn_off.assert_not_called()

    def test_execute_pickup_and_release_at_position_uses_pickup_lift_then_release_pose(self):
        events = []
        robot_service = MagicMock()
        robot_service.execute_ordered_motion_chain.side_effect = (
            lambda **kwargs: events.append([segment["label"] for segment in kwargs["segments"]]) or 0
        )
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)
        transfer_plan = PickupTransferPlan(
            pickup_approach_pose=[1, 2, 103, 180, 0, 10],
            pickup_pose=[1, 2, 3, 180, 0, 10],
            lift_pose=[1, 2, 23, 180, 0, 10],
            align_pose=[1, 2, 103, 180, 0, 0],
            stage_transition_poses=[],
            staged_pose=[4, 5, 6, 180, 0, 0],
            change_plane_pose=[1, 2, 103, 180, 0, 0],
            paint_pivot_pose=[4, 5, 6, 180, 0, 0],
        )
        executor._pickup = MagicMock()
        executor._pickup.build_plan.return_value = SimpleNamespace(
            motion_plan=transfer_plan,
            vacuum_on_before_moves=True,
        )
        executor._turn_vacuum_on = MagicMock(side_effect=lambda: events.append("vacuum_on") or (True, ""))
        executor._turn_vacuum_off = MagicMock(return_value=(True, ""))
        executor._move_pickup_phase = MagicMock(return_value=True)

        ok, msg = executor.execute_pickup_and_release_at_position(
            _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]], "pickup_xy": [1, 2]}),
            [10, 20, 30, 180, 0, 0],
            release_label="CALIBRATION",
        )

        self.assertTrue(ok, msg)
        self.assertEqual("Workpiece transferred to CALIBRATION", msg)
        executor._turn_vacuum_on.assert_called_once()
        executor._turn_vacuum_off.assert_called_once()
        executor._move_pickup_phase.assert_not_called()
        self.assertEqual(
            [
                "vacuum_on",
                [
                    "Moving to magazine pickup approach pose",
                    "Descending to magazine pickup pose",
                    "Lifting magazine workpiece",
                    "Moving picked workpiece to CALIBRATION release pose",
                ],
            ],
            events,
        )

    def test_execute_pickup_target_and_release_at_position_uses_direct_target_without_plan(self):
        events = []
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            magazine_load=PaintMagazineLoadConfig(
                transfer_to_calibration_vel_percent=31.0,
                transfer_to_calibration_acc_percent=32.0,
            )
        )
        robot_service = MagicMock()
        robot_service.execute_ordered_motion_chain.side_effect = (
            lambda **kwargs: events.append([segment["label"] for segment in kwargs["segments"]]) or 0
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            paint_process_config_service=config_service,
        )
        executor._turn_vacuum_on = MagicMock(side_effect=lambda: events.append("vacuum_on") or (True, ""))
        executor._turn_vacuum_off = MagicMock(return_value=(True, ""))
        executor._move_pickup_phase = MagicMock(return_value=True)

        ok, msg = executor.execute_pickup_target_and_release_at_position(
            pickup_xy=(11.0, 22.0),
            pickup_rz=33.0,
            pickup_base_pose=[0.0, 0.0, 0.0, 180.0, 5.0, 0.0],
            release_pose=[10.0, 20.0, 30.0, 180.0, 0.0, 0.0],
            workpiece_height_mm=7.0,
            release_label="CALIBRATION",
        )

        self.assertTrue(ok, msg)
        self.assertEqual("Workpiece transferred to CALIBRATION", msg)
        expected_pickup_z = 100.0 + 7.0 + PAINT_PROCESS_CONFIG.pickup_motion.contact_offset_mm
        expected_approach_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_motion.approach_offset_mm
        expected_lift_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_motion.initial_lift_clearance_mm
        executor._move_pickup_phase.assert_not_called()
        robot_service.execute_ordered_motion_chain.assert_called_once()
        segments = robot_service.execute_ordered_motion_chain.call_args.kwargs["segments"]
        self.assertEqual(
            [
                "vacuum_on",
                [
                    "Moving to magazine pickup approach pose",
                    "Descending to magazine pickup pose",
                    "Lifting magazine workpiece",
                    "Moving picked workpiece to CALIBRATION release pose",
                ],
            ],
            events,
        )
        self.assertEqual(segments[0]["position"], [11.0, 22.0, expected_approach_z, 180.0, 5.0, 33.0])
        self.assertEqual(segments[1]["position"], [11.0, 22.0, expected_pickup_z, 180.0, 5.0, 33.0])
        self.assertEqual(segments[2]["position"], [11.0, 22.0, expected_lift_z, 180.0, 5.0, 33.0])
        self.assertEqual(segments[3]["position"], [10.0, 20.0, 30.0, 180.0, 0.0, 0.0])
        self.assertEqual(31.0, segments[3]["vel"])
        self.assertEqual(32.0, segments[3]["acc"])

    def test_resume_pickup_target_release_continues_from_current_pose_to_next_target(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            magazine_load=PaintMagazineLoadConfig(
                transfer_to_calibration_vel_percent=31.0,
                transfer_to_calibration_acc_percent=32.0,
            )
        )
        robot_service = MagicMock()
        robot_service.get_current_position.return_value = [10.5, 21.0, 75.0, 180.0, 0.0, 0.0]
        robot_service.execute_ordered_motion_chain.return_value = 0
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            paint_process_config_service=config_service,
        )
        executor._turn_vacuum_on = MagicMock(return_value=(True, ""))
        executor._turn_vacuum_off = MagicMock(return_value=(True, ""))
        executor._move_pickup_phase = MagicMock(return_value=True)

        ok, msg = executor.execute_pickup_target_and_release_at_position(
            pickup_xy=(11.0, 22.0),
            pickup_rz=33.0,
            pickup_base_pose=[0.0, 0.0, 0.0, 180.0, 5.0, 0.0],
            release_pose=[10.0, 20.0, 30.0, 180.0, 0.0, 0.0],
            workpiece_height_mm=7.0,
            release_label="CALIBRATION",
            resume_from_current_pose=True,
        )

        self.assertTrue(ok, msg)
        robot_service.execute_ordered_motion_chain.assert_called_once()
        segments = robot_service.execute_ordered_motion_chain.call_args.kwargs["segments"]
        self.assertEqual(
            ["Moving picked workpiece to CALIBRATION release pose"],
            [segment["label"] for segment in segments],
        )
        self.assertEqual(segments[0]["position"], [10.0, 20.0, 30.0, 180.0, 0.0, 0.0])

    def test_ordered_non_contact_motion_resume_retries_remaining_waypoints(self):
        control = PaintExecutionControl()
        robot_service = MagicMock()
        robot_service.get_current_position.return_value = [5.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        robot_service.execute_ordered_motion_chain.side_effect = [-14, 0]
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)
        executor._active_execution_control = control
        segments = [
            {"type": "linear", "label": "first", "position": [0, 0, 0, 0, 0, 0], "vel": 10, "acc": 10},
            {"type": "linear", "label": "second", "position": [10, 0, 0, 0, 0, 0], "vel": 10, "acc": 10},
        ]
        result = {}

        def _run():
            result["ok"] = executor._move_ordered_pickup_sequence("resume test", segments)

        control.request_pause()
        thread = threading.Thread(target=_run)
        thread.start()
        for _ in range(100):
            if robot_service.execute_ordered_motion_chain.call_count == 1:
                break
            time.sleep(0.01)

        self.assertTrue(thread.is_alive())
        control.resume()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertTrue(result["ok"])
        self.assertEqual(robot_service.execute_ordered_motion_chain.call_count, 2)
        retry_segments = robot_service.execute_ordered_motion_chain.call_args_list[1].kwargs["segments"]
        self.assertEqual(["second"], [segment["label"] for segment in retry_segments])

    def test_execute_pickup_target_and_release_at_position_fails_without_ordered_chain(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            magazine_load=PaintMagazineLoadConfig(
                transfer_to_calibration_vel_percent=31.0,
                transfer_to_calibration_acc_percent=32.0,
            )
        )
        robot_service = MagicMock()
        robot_service.execute_ordered_motion_chain = None
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            paint_process_config_service=config_service,
        )
        executor._turn_vacuum_on = MagicMock(return_value=(True, ""))
        executor._turn_vacuum_off = MagicMock(return_value=(True, ""))
        executor._move_pickup_phase = MagicMock(return_value=True)

        ok, msg = executor.execute_pickup_target_and_release_at_position(
            pickup_xy=(11.0, 22.0),
            pickup_rz=33.0,
            pickup_base_pose=[0.0, 0.0, 0.0, 180.0, 5.0, 0.0],
            release_pose=[10.0, 20.0, 30.0, 180.0, 0.0, 0.0],
            workpiece_height_mm=7.0,
            release_label="CALIBRATION",
        )

        self.assertFalse(ok)
        self.assertEqual("Ordered motion chain is unavailable", msg)
        executor._turn_vacuum_on.assert_not_called()
        executor._turn_vacuum_off.assert_not_called()
        executor._move_pickup_phase.assert_not_called()

    def test_get_projected_pivot_paths_skips_jobs_without_paths_and_applies_offsets(self):
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            side_effect=_project,
        ):
            paths, last_pivot_pose = executor.get_projected_pivot_paths(execution_plan)

        self.assertEqual(2, len(paths))
        self.assertEqual([100.0, 200.0, 315.0, 0.0, 0.0, 90.0], captured_pivots[0][1])
        self.assertEqual([100.0, 200.0, 295.0, 0.0, 0.0, 90.0], captured_pivots[1][1])
        self.assertEqual([100.0, 200.0, 295.0, 0.0, 0.0, 90.0], last_pivot_pose)

    def test_get_pivot_motion_snapshots_returns_projected_snapshots(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [10, 20, 30, 0, 0, 0],
        )
        execution_plan = _execution_plan(
            {"execution_path": [[0, 0, 0, 0, 0, 0], [10, 0, 0, 0, 0, 0]]},
        )
        expected_snapshots = [np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=float)]

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=([], expected_snapshots, []),
        ):
            motion, last_pivot_pose = executor.get_pivot_motion_snapshots(execution_plan)

        self.assertEqual(1, len(motion))
        self.assertTrue(np.array_equal(expected_snapshots[0], motion[0][0]))
        self.assertEqual([10.0, 20.0, 30.0, 0.0, 0.0, 0.0], last_pivot_pose)

    def test_build_paint_contact_path_can_rebase_start_rotation_to_zero(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [0, 0, 0, 0, 0, 0],
        )

        with patch(
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=(
                [[1, 2, 3, 0, 0, 45], [4, 5, 6, 0, 0, 60]],
                [],
                [],
            ),
        ):
            path, _, _, _ = executor._build_paint_contact_path(
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            plan = executor._pickup.build_plan(execution_plan).motion_plan

        self.assertIsNotNone(plan)
        expected_pickup_z = 100.0 + 7.0 + PAINT_PROCESS_CONFIG.pickup_motion.contact_offset_mm
        expected_approach_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_motion.approach_offset_mm
        expected_lift_z = expected_pickup_z + PAINT_PROCESS_CONFIG.pickup_motion.initial_lift_clearance_mm
        self.assertEqual(plan.pickup_pose, [11.0, 22.0, expected_pickup_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.pickup_approach_pose, [11.0, 22.0, expected_approach_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.lift_pose, [11.0, 22.0, expected_lift_z, 180.0, 5.0, 33.0])
        self.assertEqual(plan.align_pose, [11.0, 22.0, expected_approach_z, 180.0, 5.0, 15.0])
        self.assertEqual(len(plan.staged_pose), 6)
        self.assertEqual(plan.staged_pose[5], 15.0)

    def test_pickup_plan_inserts_configured_safe_travel_waypoint_before_paint_staging(self):
        safe_pose = [70.0, 80.0, 190.0, 180.0, 0.0, 5.0]
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            safe_travel=PaintSafeTravelConfig(enabled=True, position=safe_pose)
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, 180.0, 5.0, 15.0],
            paint_process_config_service=config_service,
            pivot_motion_plane="xy_z_rz",
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [11.0, 22.0],
                "pickup_rz": 33.0,
                "workpiece_height_mm": 0.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.plan.pickup_transfer_planner.project_paint_contact_motion_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            pickup_plan = executor._pickup.build_plan(execution_plan)

        self.assertIsNotNone(pickup_plan)
        labels = [waypoint.label for waypoint in pickup_plan.waypoints]
        self.assertGreater(labels.index("Safe travel waypoint 1"), labels.index("Aligning workpiece to paint axis"))
        self.assertLess(
            labels.index("Safe travel waypoint 1"),
            labels.index("Moving to staging offset before first pivot contact pose"),
        )
        safe_waypoint = pickup_plan.waypoints[labels.index("Safe travel waypoint 1")]
        self.assertEqual(safe_pose, safe_waypoint.pose)
        self.assertEqual(PAINT_PROCESS_CONFIG.pickup_motion.stage_transition_vel_percent, safe_waypoint.vel_percent)
        self.assertEqual(PAINT_PROCESS_CONFIG.pickup_motion.stage_transition_acc_percent, safe_waypoint.acc_percent)

    def test_enabled_safe_travel_blocks_pickup_plan_when_group_position_is_missing(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            safe_travel=PaintSafeTravelConfig(enabled=True)
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pickup_base_position_provider=lambda: [10.0, 20.0, 30.0, 180.0, 5.0, 15.0],
            paint_process_config_service=config_service,
            pivot_motion_plane="xy_z_rz",
        )
        execution_plan = _execution_plan(
            {
                "execution_path": [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0]],
                "pickup_xy": [11.0, 22.0],
                "pickup_rz": 33.0,
                "workpiece_height_mm": 0.0,
            }
        )

        with patch(
            "src.robot_systems.paint.processes.paint.plan.pickup_transfer_planner.project_paint_contact_motion_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            pickup_plan = executor._pickup.build_plan(execution_plan)

        self.assertIsNone(pickup_plan)
        self.assertEqual(
            "Safe travel pose is enabled but no valid 6-axis pose is configured",
            executor._last_safe_travel_error,
        )

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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, 44.0]], [], []),
        ):
            plan = executor._pickup.build_plan(execution_plan).motion_plan

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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=([[101.0, 202.0, 303.0, 1.0, 2.0, -163.155]], [], []),
        ):
            plan = executor._pickup.build_plan(execution_plan).motion_plan

        self.assertIsNotNone(plan)
        self.assertAlmostEqual(-6.151, plan.pickup_pose[5], places=3)
        self.assertAlmostEqual(-6.151, plan.lift_pose[5], places=3)
        self.assertAlmostEqual(0.0, plan.align_pose[5], places=3)
        self.assertAlmostEqual(0.0, plan.staged_pose[5], places=3)
        self.assertAlmostEqual(6.151, plan.source_rotation_deg, places=3)

    @unittest.skip("Projection ownership moved to PaintPickupTransferPlanner")
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            side_effect=[
                ([[101.0, 202.0, 303.0, 1.0, 2.0, 10.0]], [], []),
                ([[111.0, 212.0, 313.0, 1.0, 2.0, 10.0]], [], []),
            ],
        ) as projection:
            plan = executor._pickup.build_plan(execution_plan).motion_plan

        self.assertIsNotNone(plan)
        self.assertAlmostEqual(-10.0, plan.source_rotation_deg, places=6)
        self.assertEqual([111.0, 212.0, 313.0], plan.staged_pose[:3])
        self.assertAlmostEqual(-10.0, projection.call_args_list[1].kwargs["source_rotation_deg"], places=6)

    def test_execute_paint_contact_paths_uses_carried_source_rotation(self):
        robot_service = MagicMock()
        robot_service.execute_trajectory.return_value = 0
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            base_position_provider=lambda: [100.0, 200.0, 300.0, 10.0, 20.0, 30.0],
            pivot_motion_plane="xy_z_rz",
            debug_dump_dir=None,
        )
        executor._last_pickup_plan = PickupTransferPlan(
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=(
                [[101.0, 202.0, 303.0, 1.0, 2.0, 12.0], [111.0, 202.0, 303.0, 1.0, 2.0, 12.0]],
                [],
                [],
            ),
        ) as projection:
            ok, message, total_waypoints = executor._paint_contact.execute(
                execution_plan,
                append_retreat=False,
            )

        self.assertTrue(ok, message)
        self.assertEqual(2, total_waypoints)
        self.assertGreaterEqual(len(projection.call_args_list), 1)
        self.assertAlmostEqual(12.0, projection.call_args_list[0].kwargs["source_rotation_deg"], places=6)

    def test_projected_pivot_paths_use_pickup_source_rotation_and_command_mapping(self):
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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            side_effect=_project,
        ) as projection:
            paths, _ = executor.get_projected_pivot_paths(execution_plan)

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
            "src.robot_systems.paint.processes.paint.execute.workpiece_path_executor.project_paint_contact_motion_continuous",
            return_value=([[-83.655, 316.814, 283.401, -91.478, -69.416, -0.05]], [], []),
        ):
            plan = executor._pickup.build_plan(execution_plan).motion_plan

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

        result = executor._move_pickup_phase(
            "test move",
            pose,
            velocity=PAINT_PROCESS_CONFIG.pickup_motion.approach_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_motion.approach_acc_percent,
        )

        self.assertTrue(result)
        robot_service.move_ptp.assert_called_once_with(
            position=pose,
            tool=0,
            user=0,
            velocity=PAINT_PROCESS_CONFIG.pickup_motion.approach_vel_percent,
            acceleration=PAINT_PROCESS_CONFIG.pickup_motion.approach_acc_percent,
            wait_to_reach=True,
        )

    @unittest.skip("Legacy owner-level pickup orchestration was extracted to PaintPickupExecutor")
    def test_execute_pickup_to_pivot_uses_phase_specific_motion_settings(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            enable_vacuum_pump=False,
            pivot_motion_plane="xy_z_rz",
        )
        plan = PickupTransferPlan(
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

        ok, message = executor._pickup.execute(_execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]}))

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

    @unittest.skip("Legacy owner-level pickup orchestration was extracted to PaintPickupExecutor")
    def test_execute_pickup_to_pivot_uses_deterministic_optimized_move_sequence(self):
        robot_service = MagicMock()
        robot_service.get_current_position.return_value = [0.0, 0.0, 300.0, 1.0, 2.0, 3.0]
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            enable_vacuum_pump=False,
            pivot_motion_plane="xy_z_rz",
        )
        plan = PickupTransferPlan(
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

        ok, message = executor._pickup.execute(_execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]}))

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

    @unittest.skip("Covered by PaintPickupExecutor waypoint-plan tests")
    def test_pickup_stage_lifts_with_pickup_rz_before_aligning_to_reference_rz(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            enable_vacuum_pump=False,
            pivot_motion_plane="xy_z_rz",
        )
        plan = PickupTransferPlan(
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

    @unittest.skip("Covered by PaintDropoffExecutor strategy tests")
    def test_pre_release_dropoff_does_not_restore_pickup_rz_before_release(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(robot_service=robot_service)
        executor._last_pickup_plan = PickupTransferPlan(
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

    def test_xy_rz_pre_dropoff_unwind_does_not_move_to_align_pose_before_unwind(self):
        events = []
        robot_service = MagicMock()
        robot_service.move_ptp.side_effect = lambda **_kwargs: events.append("align") or True
        robot_service.unwind_joint6.side_effect = lambda **_kwargs: events.append("unwind") or True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            pivot_motion_plane="xy_z_rz",
        )
        executor._last_pickup_plan = PickupTransferPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, 5.0],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 15.0],
            stage_transition_poses=[],
            staged_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
            change_plane_pose=[10.0, 20.0, 100.0, 90.0, 0.0, 15.0],
            paint_pivot_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
        )

        ok, message = executor._prepare_dropoff_joint6_unwind()

        self.assertTrue(ok, message)
        self.assertEqual(["unwind"], events)
        robot_service.move_ptp.assert_not_called()

    def test_xy_rz_ordered_dropoff_preparation_unwinds_without_align_move(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            pivot_motion_plane="xy_z_rz",
        )
        executor._last_pickup_plan = PickupTransferPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, 5.0],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 5.0],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 15.0],
            stage_transition_poses=[],
            staged_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
            change_plane_pose=[10.0, 20.0, 100.0, 90.0, 0.0, 15.0],
            paint_pivot_pose=[30.0, 40.0, 110.0, 90.0, 0.0, 15.0],
        )

        segments, final_pose = executor._ordered_dropoff_preparation_segments()

        self.assertEqual(["unwind_joint6"], [segment["type"] for segment in segments])
        self.assertEqual(["prepare_dropoff_unwind"], [segment["label"] for segment in segments])
        self.assertIsNone(final_pose)

    def test_xy_rz_current_dropoff_releases_without_align_pose_wrap_move(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            pivot_motion_plane="xy_z_rz",
        )
        executor._configured_contact_motion_plane = "xy_z_rz"
        executor._last_process_end_pose = [294.527, 403.861, 91.129, -178.852, -0.014, 359.959]
        executor._last_pickup_plan = PickupTransferPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, -0.270],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, -0.270],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, -0.270],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 0.0],
            stage_transition_poses=[],
            staged_pose=[284.599, 404.100, 101.129, -178.852, -0.014, 0.0],
            change_plane_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 0.0],
            paint_pivot_pose=[284.599, 404.100, 101.129, -178.852, -0.014, 0.0],
        )

        segments, final_pose = executor._ordered_dropoff_preparation_segments()

        self.assertEqual(["prepare_dropoff_unwind"], [segment["label"] for segment in segments])
        self.assertIsNone(final_pose)

    def test_xy_rz_dropoff_releases_at_current_pose_without_restore_move(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            pivot_motion_plane="xy_z_rz",
        )
        executor._configured_contact_motion_plane = "xy_z_rz"
        executor._last_process_end_pose = [294.527, 403.861, 91.129, -178.852, -0.014, 359.959]
        executor._last_pickup_plan = PickupTransferPlan(
            pickup_approach_pose=[10.0, 20.0, 100.0, 180.0, 0.0, -0.270],
            pickup_pose=[10.0, 20.0, 50.0, 180.0, 0.0, -0.270],
            lift_pose=[10.0, 20.0, 100.0, 180.0, 0.0, -0.270],
            align_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 0.0],
            stage_transition_poses=[],
            staged_pose=[284.599, 404.100, 101.129, -178.852, -0.014, 0.0],
            change_plane_pose=[10.0, 20.0, 100.0, 180.0, 0.0, 0.0],
            paint_pivot_pose=[284.599, 404.100, 101.129, -178.852, -0.014, 0.0],
        )

        ok, message = executor._dropoff.execute(_execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]}))

        self.assertTrue(ok, message)
        robot_service.move_ptp.assert_not_called()

    def test_xy_rz_movement_group_dropoff_moves_to_configured_group_before_release(self):
        robot_service = MagicMock()
        robot_service.move_ptp.return_value = True
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            pivot_motion_plane="xy_z_rz",
            dropoff=PaintDropoffConfig(
                strategy="movement_group",
                release_align_vel_percent=12.0,
                release_align_acc_percent=13.0,
            ),
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            pivot_motion_plane="xy_z_rz",
            dropoff_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            paint_process_config_service=config_service,
        )
        executor._configured_contact_motion_plane = "xy_z_rz"
        executor._refresh_paint_process_config_snapshot()

        ok, message = executor._dropoff.execute(_execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]}))

        self.assertTrue(ok, message)
        robot_service.move_ptp.assert_called_once_with(
            position=[1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            tool=0,
            user=0,
            velocity=12.0,
            acceleration=13.0,
            wait_to_reach=True,
        )

    def test_xy_rz_movement_group_dropoff_preparation_moves_to_dropoff_before_unwind(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            pivot_motion_plane="xy_z_rz",
            dropoff=PaintDropoffConfig(
                strategy="movement_group",
                release_align_vel_percent=12.0,
                release_align_acc_percent=13.0,
            ),
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            pivot_motion_plane="xy_z_rz",
            dropoff_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            paint_process_config_service=config_service,
        )
        executor._configured_contact_motion_plane = "xy_z_rz"
        executor._refresh_paint_process_config_snapshot()

        segments, final_pose = executor._ordered_dropoff_preparation_segments()

        self.assertEqual(["prepare_dropoff_align", "prepare_dropoff_unwind"], [segment["label"] for segment in segments])
        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], final_pose)
        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], segments[0]["position"])
        self.assertEqual(12.0, segments[0]["vel"])
        self.assertEqual(13.0, segments[0]["acc"])

    def test_paint_to_dropoff_safe_travel_precedes_dropoff_align_before_unwind(self):
        safe_pose = [7.0, 8.0, 9.0, 10.0, 11.0, 12.0]
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            pivot_motion_plane="xy_z_rz",
            dropoff=PaintDropoffConfig(
                strategy="movement_group",
                release_align_vel_percent=12.0,
                release_align_acc_percent=13.0,
            ),
            dropoff_safe_travel=PaintToDropoffSafeTravelConfig(
                enabled=True,
                position=safe_pose,
            ),
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            pivot_motion_plane="xy_z_rz",
            dropoff_position_provider=lambda: [1.0, 2.0, 3.0, 4.0, 5.0, 6.0],
            paint_process_config_service=config_service,
        )
        executor._configured_contact_motion_plane = "xy_z_rz"
        executor._refresh_paint_process_config_snapshot()

        segments, final_pose = executor._ordered_dropoff_preparation_segments()

        self.assertEqual(
            ["prepare_dropoff_safe_travel", "prepare_dropoff_align", "prepare_dropoff_unwind"],
            [segment["label"] for segment in segments],
        )
        self.assertEqual(safe_pose, segments[0]["position"])
        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], final_pose)
        self.assertEqual(12.0, segments[0]["vel"])
        self.assertEqual(13.0, segments[0]["acc"])

    def test_enabled_paint_to_dropoff_safe_travel_without_pose_blocks_dropoff_preparation(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            pivot_motion_plane="xy_z_rz",
            dropoff_safe_travel=PaintToDropoffSafeTravelConfig(enabled=True),
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            pivot_motion_plane="xy_z_rz",
            paint_process_config_service=config_service,
        )
        executor._configured_contact_motion_plane = "xy_z_rz"
        executor._refresh_paint_process_config_snapshot()

        ok, message = executor._prepare_dropoff_joint6_unwind()

        self.assertFalse(ok)
        self.assertEqual("Pivot paint finished, but paint-to-dropoff safe travel pose is not configured", message)

    def test_xz_ry_ordered_dropoff_preparation_uses_configured_dropoff_group(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            pivot_motion_plane="xz_y_ry",
            dropoff=PaintDropoffConfig(
                strategy="movement_group",
                release_align_vel_percent=14.0,
                release_align_acc_percent=15.0,
            ),
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            pivot_motion_plane="xz_y_ry",
            dropoff_position_provider=lambda: [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
            paint_process_config_service=config_service,
        )
        executor._configured_contact_motion_plane = "xz_y_ry"
        executor._refresh_paint_process_config_snapshot()

        segments, final_pose = executor._ordered_dropoff_preparation_segments()

        self.assertEqual(["prepare_dropoff_align", "prepare_dropoff_unwind"], [segment["label"] for segment in segments])
        self.assertEqual([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], final_pose)
        self.assertEqual([10.0, 20.0, 30.0, 40.0, 50.0, 60.0], segments[0]["position"])
        self.assertEqual(14.0, segments[0]["vel"])
        self.assertEqual(15.0, segments[0]["acc"])

    def test_dropoff_pose_close_treats_wrapped_xy_rz_as_same_release_pose(self):
        self.assertTrue(
            _poses_close(
                [10.0, 20.0, 100.0, 180.0, 0.0, 0.0],
                [10.0, 20.0, 100.0, 180.0, 0.0, 360.0],
            )
        )
        self.assertFalse(
            _poses_close(
                [10.0, 20.0, 100.0, 180.0, 0.0, 180.0],
                [10.0, 20.0, 100.0, 180.0, 0.0, 360.0],
            )
        )

    def test_execute_paint_process_runs_post_execute_return_after_success(self):
        post_execute_callback = MagicMock(return_value=True)
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=post_execute_callback,
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(True, "", 3))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_paint_process(plan)

        self.assertTrue(ok)
        self.assertIn("3 waypoints", msg)
        post_execute_callback.assert_called_once_with()

    def test_execute_paint_process_pauses_after_contact_before_dropoff(self):
        control = PaintExecutionControl()
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=True),
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._edge_cleanup.should_run_after_xy_rz = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})
        result = {}

        def _contact(_plan, *, control=None):
            control.request_pause()
            return True, "", 3

        executor._paint_contact.execute = MagicMock(side_effect=_contact)
        thread = threading.Thread(
            target=lambda: result.update(value=executor.execute_paint_process(plan, control=control))
        )

        thread.start()
        for _ in range(100):
            if executor._paint_contact.execute.called and not executor._dropoff.execute.called:
                break
            time.sleep(0.01)

        self.assertTrue(thread.is_alive())
        executor._dropoff.execute.assert_not_called()

        control.resume()
        thread.join(timeout=1.0)

        self.assertFalse(thread.is_alive())
        self.assertTrue(result["value"][0], result["value"][1])
        executor._dropoff.execute.assert_called_once_with(plan)

    def test_execute_paint_process_logs_timing_summary_after_cycle(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(enable_path_debug_plots=True)
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=True),
            debug_dump_dir="/tmp/paint-timing",
            paint_process_config_service=config_service,
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(True, "", 3))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._edge_cleanup.should_run_after_xy_rz = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        with (
            patch("src.robot_systems.paint.timing.TimingRecorder.write_csv", return_value="/tmp/timing.csv") as write_csv,
            patch("src.robot_systems.paint.timing.TimingRecorder.log_summary") as log_summary,
        ):
            ok, msg = executor.execute_paint_process(plan)

        self.assertTrue(ok, msg)
        write_csv.assert_called_once_with("/tmp/paint-timing")
        log_summary.assert_called_once()
        self.assertEqual(log_summary.call_args.kwargs["csv_path"], "/tmp/timing.csv")

    def test_execute_paint_process_skips_timing_csv_when_diagnostics_are_disabled(self):
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(
            enable_path_debug_plots=False,
            enable_pivot_debug_plot=False,
            enable_execution_motion_trace=False,
        )
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=True),
            debug_dump_dir="/tmp/paint-timing",
            paint_process_config_service=config_service,
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(True, "", 3))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._edge_cleanup.should_run_after_xy_rz = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        with (
            patch("src.robot_systems.paint.timing.TimingRecorder.write_csv") as write_csv,
            patch("src.robot_systems.paint.timing.TimingRecorder.log_summary") as log_summary,
        ):
            ok, msg = executor.execute_paint_process(plan)

        self.assertTrue(ok, msg)
        write_csv.assert_not_called()
        log_summary.assert_called_once()
        self.assertIsNone(log_summary.call_args.kwargs["csv_path"])

    def test_xy_rz_cleanup_unwinds_without_calibration_before_cleanup(self):
        events = []
        robot_service = MagicMock()

        def _calibration_return():
            events.append("calibration")
            return True

        def _unwind_joint6(**_kwargs):
            events.append("unwind")
            return True

        def _cleanup(_plan, _started, *, unwind_before_cleanup=True):
            events.append(("cleanup", unwind_before_cleanup))
            return True, "", 5

        robot_service.unwind_joint6.side_effect = _unwind_joint6
        robot_service.execute_ordered_motion_chain = None
        config_service = MagicMock()
        config_service.get_snapshot.return_value = PaintProcessConfig(pivot_motion_plane="xy_z_rz")
        executor = PaintWorkpiecePathExecutor(
            robot_service=robot_service,
            post_execute_callback=_calibration_return,
            paint_process_config_service=config_service,
        )
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(True, "", 3))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._edge_cleanup.should_run_after_xy_rz = MagicMock(return_value=True)
        executor._edge_cleanup.execute_after_xy_rz_paint = MagicMock(side_effect=_cleanup)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_paint_process(plan)

        self.assertTrue(ok, msg)
        self.assertEqual([("cleanup", True), "calibration"], events)

    def test_execute_paint_process_fails_when_post_execute_return_fails(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=False),
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(True, "", 3))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(True, ""))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_paint_process(plan)

        self.assertFalse(ok)
        self.assertEqual("Paint process finished, but return-to-calibration failed", msg)

    def test_execute_paint_process_returns_to_calibration_after_paint_contact_failure(self):
        post_execute_callback = MagicMock(return_value=True)
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=post_execute_callback,
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(False, "pivot failed", 0))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_paint_process(plan)

        self.assertFalse(ok)
        self.assertEqual("pivot failed", msg)
        post_execute_callback.assert_called_once_with()

    def test_execute_paint_process_reports_cleanup_failure_after_motion_failure(self):
        executor = PaintWorkpiecePathExecutor(
            robot_service=MagicMock(),
            post_execute_callback=MagicMock(return_value=False),
        )
        executor._robot_service.execute_ordered_motion_chain = None
        executor._pickup.execute = MagicMock(return_value=(True, "pickup ok"))
        executor._paint_contact.execute = MagicMock(return_value=(True, "", 3))
        executor._edge_cleanup.should_run_after_xz_ry = MagicMock(return_value=False)
        executor._prepare_dropoff_joint6_unwind = MagicMock(return_value=(True, ""))
        executor._dropoff.execute = MagicMock(return_value=(False, "restore failed"))
        plan = _execution_plan({"execution_path": [[0, 0, 0, 0, 0, 0]]})

        ok, msg = executor.execute_paint_process(plan)

        self.assertFalse(ok)
        self.assertEqual("restore failed; additionally, return-to-calibration failed", msg)

    def test_build_executed_snapshot_series_rebases_preview_snapshot_to_executed_poses(self):
        pivot_config = _normalize_contact_motion_config(motion_plane="xy_z_rz")
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
        pivot_config = _normalize_contact_motion_config(motion_plane="xy_z_rz")
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
