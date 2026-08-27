from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import ANY, MagicMock

from src.robot_systems.paint import application_wiring
from src.robot_systems.paint.applications.paint_process_settings.mapper import PaintProcessSettingsMapper
from src.robot_systems.paint.applications.paint_process_settings.view.paint_process_settings_schema import (
    build_paint_process_settings_tabs,
)
from src.robot_systems.paint.applications.paint_motion_plane_setup.domain.plane_inference import (
    Pose6D,
    infer_plane,
)
from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintContactStagingConfig,
    PaintEdgeCleanupConfig,
    PaintMagazineLoadConfig,
    PaintProcessConfig,
    PaintSafeTravelConfig,
    PaintSimulationConfig,
)
from src.robot_systems.paint.processes.paint.paint_process_config_serializer import PaintProcessConfigSerializer
from src.robot_systems.paint.processes.paint.execute.edge_cleanup_executor import PaintEdgeCleanupExecutor
from src.robot_systems.paint.processes.paint.execute.paint_contact_executor import PaintContactExecutor
from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import (
    PaintWorkpiecePathExecutor,
    _camera_to_tcp_delta,
    _normalize_contact_motion_config,
)


class TestPaintProcessConfig(unittest.TestCase):
    def test_contact_staging_settings_roundtrip_through_ui_and_serializer(self) -> None:
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)
        flat.update({
            "staging_attach_z_offset_mm": 1.0,
            "staging_attach_paint_axis_offset_mm": 2.0,
            "staging_attach_perpendicular_axis_offset_mm": 3.0,
            "staging_detach_z_offset_mm": 4.0,
            "staging_detach_paint_axis_offset_mm": 5.0,
            "staging_detach_perpendicular_axis_offset_mm": 6.0,
        })

        mapped = PaintProcessSettingsMapper.from_flat_dict(flat, base)
        restored = PaintProcessConfigSerializer().from_dict(
            PaintProcessConfigSerializer().to_dict(mapped)
        )

        self.assertEqual(
            PaintContactStagingConfig(1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            restored.contact_staging,
        )

    def test_distance_offsets_tab_exposes_attach_and_detach_staging_offsets(self) -> None:
        distance_groups = dict(build_paint_process_settings_tabs())["Distances & Offsets"]
        keys = [field.key for group in distance_groups for field in group.fields]

        self.assertIn("staging_attach_perpendicular_axis_offset_mm", keys)
        self.assertIn("staging_detach_perpendicular_axis_offset_mm", keys)

    def test_process_config_derived_properties_follow_motion_plane(self) -> None:
        default_config = PaintProcessConfig()

        self.assertEqual(PAINT_PROCESS_CONFIG.primary_group_id, "Vertical Shaft")
        self.assertEqual(default_config.primary_group_id, "Vertical Shaft")
        self.assertEqual(default_config.secondary_group_id, "Horizontal Shaft")
        self.assertEqual(default_config.cleanup_group_id, "Clean")
        self.assertEqual(default_config.pivot_contact_side, "positive")
        self.assertFalse(default_config.magazine_load.enabled)
        self.assertEqual(default_config.magazine_load.magazine_group_id, "Magazine")
        self.assertEqual(default_config.magazine_load.calibration_group_id, "CALIBRATION")
        self.assertEqual(default_config.magazine_load.move_to_magazine_vel_percent, 30.0)
        self.assertEqual(default_config.magazine_load.move_to_magazine_acc_percent, 30.0)
        self.assertEqual(default_config.magazine_load.transfer_to_calibration_vel_percent, 30.0)
        self.assertEqual(default_config.magazine_load.transfer_to_calibration_acc_percent, 30.0)
        self.assertFalse(default_config.safe_travel.enabled)
        self.assertEqual(default_config.safe_travel.position, [])
        self.assertFalse(default_config.dropoff_safe_travel.enabled)
        self.assertEqual(default_config.dropoff_safe_travel.position, [])
        self.assertFalse(default_config.enable_path_debug_plots)

        original = application_wiring._PAINT_PROCESS
        try:
            application_wiring._PAINT_PROCESS = PaintProcessConfig(pivot_motion_plane="xy_z_rz")
            self.assertEqual(application_wiring._get_paint_base_group_id(), "Vertical Shaft")

            application_wiring._PAINT_PROCESS = PaintProcessConfig(pivot_motion_plane="xz_y_ry")
            self.assertEqual(application_wiring._get_paint_base_group_id(), "Horizontal Shaft")
            self.assertEqual(application_wiring._get_cleanup_base_group_id(), "Clean")
        finally:
            application_wiring._PAINT_PROCESS = original

    def test_process_config_exposes_pickup_defaults_used_by_executor(self) -> None:
        default_config = PaintProcessConfig()

        self.assertEqual(default_config.pickup_motion.approach_offset_mm, 100.0)
        self.assertEqual(default_config.pickup_motion.contact_offset_mm, 5.0)
        self.assertEqual(default_config.pickup_motion.initial_lift_clearance_mm, 20.0)
        self.assertEqual(default_config.pickup_motion.approach_vel_percent, 60.0)
        self.assertEqual(default_config.pickup_motion.approach_acc_percent, 50.0)
        self.assertEqual(default_config.pickup_motion.descend_vel_percent, 60.0)
        self.assertEqual(default_config.pickup_motion.descend_acc_percent, 40.0)
        self.assertEqual(default_config.pickup_motion.lift_align_vel_percent, 80.0)
        self.assertEqual(default_config.pickup_motion.lift_align_acc_percent, 40.0)
        self.assertEqual(default_config.pickup_motion.change_plane_vel_percent, 80.0)
        self.assertEqual(default_config.pickup_motion.change_plane_acc_percent, 40.0)
        self.assertEqual(default_config.pickup_motion.stage_transition_vel_percent, 50.0)
        self.assertEqual(default_config.pickup_motion.stage_transition_acc_percent, 20.0)
        self.assertEqual(default_config.pickup_motion.first_contact_vel_percent, 80.0)
        self.assertEqual(default_config.pickup_motion.first_contact_acc_percent, 30.0)
        self.assertEqual(default_config.interpolation.path_tangent_lookahead_mm, 15.0)
        self.assertEqual(default_config.interpolation.path_tangent_deadband_deg, 5.0)

    def test_process_settings_mapper_roundtrips_interpolation_settings(self) -> None:
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)

        self.assertEqual(flat["path_tangent_lookahead_mm"], 15.0)
        self.assertEqual(flat["path_tangent_deadband_deg"], 5.0)

        restored = PaintProcessSettingsMapper.from_flat_dict(
            {
                **flat,
                "path_tangent_lookahead_mm": 22.5,
                "path_tangent_deadband_deg": 3.5,
            },
            base,
        )

        self.assertEqual(restored.interpolation.path_tangent_lookahead_mm, 22.5)
        self.assertEqual(restored.interpolation.path_tangent_deadband_deg, 3.5)

    def test_process_settings_mapper_roundtrips_default_paint_motion(self) -> None:
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)

        self.assertEqual(10.0, flat["default_paint_velocity_percent"])
        self.assertEqual(10.0, flat["default_paint_acceleration_percent"])
        self.assertEqual(0.0, flat["default_paint_offset_mm"])

        restored = PaintProcessSettingsMapper.from_flat_dict(
            {
                **flat,
                "default_paint_velocity_percent": 25.0,
                "default_paint_acceleration_percent": 35.0,
                "default_paint_offset_mm": -4.5,
            },
            base,
        )

        self.assertEqual(25.0, restored.default_paint_velocity_percent)
        self.assertEqual(35.0, restored.default_paint_acceleration_percent)
        self.assertEqual(-4.5, restored.default_paint_offset_mm)

    def test_process_settings_mapper_roundtrips_magazine_load_settings(self) -> None:
        base = PaintProcessConfig(magazine_load=PaintMagazineLoadConfig(enabled=False))
        flat = PaintProcessSettingsMapper.to_flat_dict(base)

        self.assertFalse(flat["magazine_load_enabled"])
        self.assertTrue(flat["run_while_workpiece_found"])
        self.assertTrue(flat["enable_execution_state_timing"])
        self.assertEqual(0.5, flat["magazine_camera_settle_s"])
        self.assertEqual(0.5, flat["magazine_release_settle_s"])
        self.assertEqual(50.0, flat["magazine_release_z_mm"])
        self.assertEqual(30.0, flat["magazine_move_to_magazine_vel_percent"])
        self.assertEqual(30.0, flat["magazine_move_to_magazine_acc_percent"])
        self.assertEqual(30.0, flat["magazine_transfer_to_calibration_vel_percent"])
        self.assertEqual(30.0, flat["magazine_transfer_to_calibration_acc_percent"])

        restored = PaintProcessSettingsMapper.from_flat_dict(
            {
                **flat,
                "magazine_load_enabled": True,
                "run_while_workpiece_found": False,
                "enable_execution_state_timing": False,
                "magazine_camera_settle_s": 0.25,
                "magazine_release_settle_s": 0.75,
                "magazine_release_z_mm": 55.0,
                "magazine_move_to_magazine_vel_percent": 11.0,
                "magazine_move_to_magazine_acc_percent": 12.0,
                "magazine_transfer_to_calibration_vel_percent": 13.0,
                "magazine_transfer_to_calibration_acc_percent": 14.0,
            },
            base,
        )

        self.assertTrue(restored.magazine_load.enabled)
        self.assertFalse(restored.run_while_workpiece_found)
        self.assertFalse(restored.enable_execution_state_timing)
        self.assertEqual(0.25, restored.magazine_load.camera_settle_s)
        self.assertEqual(0.75, restored.magazine_load.release_settle_s)
        self.assertEqual(55.0, restored.magazine_load.release_z_mm)
        self.assertEqual(11.0, restored.magazine_load.move_to_magazine_vel_percent)
        self.assertEqual(12.0, restored.magazine_load.move_to_magazine_acc_percent)
        self.assertEqual(13.0, restored.magazine_load.transfer_to_calibration_vel_percent)
        self.assertEqual(14.0, restored.magazine_load.transfer_to_calibration_acc_percent)

    def test_process_settings_mapper_roundtrips_safe_travel_settings(self) -> None:
        base = PaintProcessConfig(safe_travel=PaintSafeTravelConfig(enabled=False))
        flat = PaintProcessSettingsMapper.to_flat_dict(base)

        self.assertFalse(flat["safe_travel_enabled"])
        self.assertEqual("", flat["safe_travel_position"])

        restored = PaintProcessSettingsMapper.from_flat_dict(
            {
                **flat,
                "safe_travel_enabled": True,
                "safe_travel_position": "1, 2, 3, 4, 5, 6",
            },
            base,
        )

        self.assertTrue(restored.safe_travel.enabled)
        self.assertEqual([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], restored.safe_travel.position)

    def test_process_settings_mapper_roundtrips_dropoff_safe_travel_settings(self) -> None:
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)

        self.assertFalse(flat["dropoff_safe_travel_enabled"])
        self.assertEqual("", flat["dropoff_safe_travel_position"])

        restored = PaintProcessSettingsMapper.from_flat_dict(
            {
                **flat,
                "dropoff_safe_travel_enabled": True,
                "dropoff_safe_travel_position": "7, 8, 9, 10, 11, 12",
            },
            base,
        )

        self.assertTrue(restored.dropoff_safe_travel.enabled)
        self.assertEqual([7.0, 8.0, 9.0, 10.0, 11.0, 12.0], restored.dropoff_safe_travel.position)

    def test_process_settings_mapper_roundtrips_diagnostics_settings(self) -> None:
        base = PaintProcessConfig()
        flat = PaintProcessSettingsMapper.to_flat_dict(base)

        self.assertFalse(flat["enable_path_debug_plots"])

        restored = PaintProcessSettingsMapper.from_flat_dict(
            {**flat, "enable_path_debug_plots": True},
            base,
        )

        self.assertTrue(restored.enable_path_debug_plots)

    def test_process_config_serializer_roundtrips_magazine_load_section(self) -> None:
        serializer = PaintProcessConfigSerializer()
        config = PaintProcessConfig(
            run_while_workpiece_found=False,
            magazine_load=PaintMagazineLoadConfig(
                enabled=True,
                magazine_group_id="Magazine",
                calibration_group_id="CALIBRATION",
                move_to_magazine_vel_percent=21.0,
                move_to_magazine_acc_percent=22.0,
                transfer_to_calibration_vel_percent=23.0,
                transfer_to_calibration_acc_percent=24.0,
                release_z_mm=50.0,
                camera_settle_s=1.25,
                release_settle_s=0.75,
            )
        )

        restored = serializer.from_dict(serializer.to_dict(config))

        self.assertTrue(restored.magazine_load.enabled)
        self.assertFalse(restored.run_while_workpiece_found)
        self.assertEqual("Magazine", restored.magazine_load.magazine_group_id)
        self.assertEqual("CALIBRATION", restored.magazine_load.calibration_group_id)
        self.assertEqual(21.0, restored.magazine_load.move_to_magazine_vel_percent)
        self.assertEqual(22.0, restored.magazine_load.move_to_magazine_acc_percent)
        self.assertEqual(23.0, restored.magazine_load.transfer_to_calibration_vel_percent)
        self.assertEqual(24.0, restored.magazine_load.transfer_to_calibration_acc_percent)
        self.assertEqual(50.0, restored.magazine_load.release_z_mm)
        self.assertEqual(1.25, restored.magazine_load.camera_settle_s)
        self.assertEqual(0.75, restored.magazine_load.release_settle_s)

    def test_process_config_serializer_roundtrips_safe_travel_section(self) -> None:
        serializer = PaintProcessConfigSerializer()
        config = PaintProcessConfig(
            safe_travel=PaintSafeTravelConfig(enabled=True, position=[1, 2, 3, 4, 5, 6])
        )

        restored = serializer.from_dict(serializer.to_dict(config))

        self.assertTrue(restored.safe_travel.enabled)
        self.assertEqual([1, 2, 3, 4, 5, 6], restored.safe_travel.position)

    def test_process_settings_schema_has_interpolation_tab(self) -> None:
        tabs = build_paint_process_settings_tabs()
        interpolation = dict(tabs)["Interpolation"]
        keys = [field.key for group in interpolation for field in group.fields]

        self.assertEqual(keys, ["path_tangent_lookahead_mm", "path_tangent_deadband_deg"])

    def test_default_paint_motion_controls_are_under_motion_speeds(self) -> None:
        tabs = dict(build_paint_process_settings_tabs())
        process_keys = [field.key for group in tabs["Process"] for field in group.fields]
        motion_keys = [field.key for group in tabs["Motion Speeds"] for field in group.fields]

        self.assertNotIn("default_paint_velocity_percent", process_keys)
        self.assertNotIn("default_paint_acceleration_percent", process_keys)
        self.assertIn("default_paint_velocity_percent", motion_keys)
        self.assertIn("default_paint_offset_mm", motion_keys)
        self.assertIn("default_paint_acceleration_percent", motion_keys)

    def test_process_settings_schema_has_magazine_load_motion_speed_controls(self) -> None:
        tabs = build_paint_process_settings_tabs()
        motion_speeds = dict(tabs)["Motion Speeds"]
        magazine_groups = [group for group in motion_speeds if group.title == "Magazine Load"]

        self.assertEqual(1, len(magazine_groups))
        self.assertEqual(
            [
                "magazine_move_to_magazine_vel_percent",
                "magazine_move_to_magazine_acc_percent",
                "magazine_transfer_to_calibration_vel_percent",
                "magazine_transfer_to_calibration_acc_percent",
            ],
            [field.key for field in magazine_groups[0].fields],
        )

    def test_process_settings_schema_has_process_tab_controls(self) -> None:
        tabs = build_paint_process_settings_tabs()
        process = dict(tabs)["Process"]
        keys = [field.key for group in process for field in group.fields]
        safe_travel_groups = [group for group in process if group.title == "Safe Travel"]

        self.assertIn("run_while_workpiece_found", keys)
        self.assertIn("enable_execution_state_timing", keys)
        self.assertIn("magazine_load_enabled", keys)
        self.assertIn("magazine_release_z_mm", keys)
        self.assertIn("magazine_camera_settle_s", keys)
        self.assertIn("magazine_release_settle_s", keys)
        self.assertIn("safe_travel_enabled", keys)
        self.assertIn("safe_travel_position", keys)
        self.assertIn("safe_travel_set_current", keys)
        self.assertIn("dropoff_safe_travel_enabled", keys)
        self.assertIn("dropoff_safe_travel_position", keys)
        self.assertIn("dropoff_safe_travel_set_current", keys)
        self.assertNotIn("safe_travel_group_id", keys)
        self.assertEqual(1, len(safe_travel_groups))
        self.assertEqual(
            [
                "safe_travel_enabled",
                "safe_travel_position",
                "safe_travel_set_current",
                "dropoff_safe_travel_enabled",
                "dropoff_safe_travel_position",
                "dropoff_safe_travel_set_current",
            ],
            [field.key for field in safe_travel_groups[0].fields],
        )

        diagnostics = dict(tabs)["Diagnostics"]
        diagnostics_keys = [field.key for group in diagnostics for field in group.fields]
        self.assertIn("enable_path_debug_plots", diagnostics_keys)

    def test_executor_contact_motion_plane_refreshes_from_config_service(self) -> None:
        service = type(
            "_Service",
            (),
            {
                "get_snapshot": lambda _self: PaintProcessConfig(
                    pivot_motion_plane="xy_z_rz",
                    primary_group_id="Vertical Shaft",
                    secondary_group_id="Horizontal Shaft",
                )
            },
        )()
        executor = PaintWorkpiecePathExecutor(
            robot_service=None,
            pivot_motion_plane="xz_y_ry",
            paint_process_config_service=service,
        )

        executor._refresh_paint_process_config_snapshot()
        executor._apply_paint_process_contact_config()

        self.assertEqual(executor._configured_contact_motion_plane, "xy_z_rz")
        self.assertEqual(executor._contact_motion_config.motion_plane, "xy_z_rz")

    def test_edge_cleanup_has_separate_xy_rz_enable_gate(self) -> None:
        config = PaintProcessConfig(
            edge_cleanup=PaintEdgeCleanupConfig(
                enabled_after_xz_ry=False,
                enabled_after_xy_rz=True,
            )
        )
        owner = type(
            "_Owner",
            (),
            {
                "_configured_contact_motion_plane": "xy_z_rz",
                "_paint_process_config": lambda _self: config,
            },
        )()

        cleanup = PaintEdgeCleanupExecutor(owner)

        self.assertTrue(cleanup.should_run_after_xy_rz())
        self.assertFalse(cleanup.should_run_after_xz_ry())

    def test_xy_rz_cleanup_fails_before_clean_move_when_unwind_fails(self) -> None:
        config = PaintProcessConfig(
            edge_cleanup=PaintEdgeCleanupConfig(enabled_after_xy_rz=True)
        )
        owner = SimpleNamespace(
            _base_position_provider=lambda: [1, 2, 3, 4, 5, 6],
            _pickup_base_position_provider=lambda: [1, 2, 3, 4, 5, 6],
            _contact_motion_config=SimpleNamespace(motion_plane="xy_z_rz"),
            _contact_motion_strategy=object(),
            _active_contact_base_z_offset_mm=0.0,
            _paint_process_config=lambda: config,
            _resolve_cleanup_base_position=lambda: [10, 20, 30, 0, 0, 0],
            _set_runtime_contact_motion_config=MagicMock(),
            _make_runtime_contact_motion_config=MagicMock(return_value=SimpleNamespace(motion_plane="xy_z_rz")),
        )
        cleanup = PaintEdgeCleanupExecutor(owner)
        cleanup._preplan_cleanup_path = MagicMock(
            return_value=SimpleNamespace(
                ok=True,
                message="",
                total_waypoints=7,
                stage_approach_pose=[10, 20, 30, 0, 0, 0],
                command_path=[[10, 20, 30, 0, 0, 0]],
            )
        )
        cleanup.unwind_joint6_before_cleanup = MagicMock(return_value=(False, "unwind failed"))
        cleanup._move_to_preplanned_xy_rz_stage = MagicMock()

        ok, msg, waypoints = cleanup.execute_after_xy_rz_paint(SimpleNamespace(), started=0.0)

        self.assertFalse(ok)
        self.assertEqual(msg, "unwind failed")
        self.assertEqual(waypoints, 7)
        cleanup._move_to_preplanned_xy_rz_stage.assert_not_called()

    def test_edge_cleanup_uses_ordered_chain_generic_segments(self) -> None:
        config = PaintProcessConfig()
        robot = SimpleNamespace(
            execute_ordered_motion_chain=MagicMock(return_value=0),
        )
        owner = SimpleNamespace(
            _robot_service=robot,
            _pickup_tool=3,
            _pickup_user=4,
            _paint_process_config=lambda: config,
            _configured_contact_motion_plane="xy_z_rz",
            _last_pickup_plan=None,
            _dropoff_unwind_prepared=False,
            _last_process_end_pose=None,
        )
        cleanup = PaintEdgeCleanupExecutor(owner)

        ok, msg, waypoints = cleanup._execute_ordered_cleanup_chain(
            [0, 1, 2, 3, 4, 5],
            [1, 2, 3, 4, 5, 6],
            [[1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 7]],
            started=0.0,
        )

        self.assertTrue(ok, msg)
        self.assertEqual(waypoints, 2)
        robot.execute_ordered_motion_chain.assert_called_once()
        segments = robot.execute_ordered_motion_chain.call_args.args[0]
        self.assertEqual([segment["type"] for segment in segments], ["linear", "unwind_joint6", "linear", "path", "unwind_joint6"])

    def test_paint_contact_starts_cleanup_preplan_before_final_robot_execute(self) -> None:
        events: list[str] = []
        robot = SimpleNamespace(
            execute_trajectory=MagicMock(side_effect=lambda *args, **kwargs: events.append("execute") or 0),
        )
        edge_cleanup = SimpleNamespace(
            start_preplanning_during_paint=MagicMock(
                side_effect=lambda *args, **kwargs: events.append("preplan")
            )
        )
        owner = SimpleNamespace(
            _robot_service=robot,
            _edge_cleanup=edge_cleanup,
            _debug_dump_dir=None,
            _contact_motion_config=PaintSimulationConfig(),
            _configured_contact_motion_plane="xy_z_rz",
            _last_pickup_plan=None,
            _last_process_start_rz=None,
            _last_process_end_pose=None,
            _refresh_runtime_config=MagicMock(),
            _paint_process_config=lambda: PaintProcessConfig(),
            _resolve_pivot_offset_mm=MagicMock(return_value=0.0),
            _build_paint_contact_path=MagicMock(
                return_value=(
                    [[1.0, 2.0, 3.0, 180.0, 0.0, 0.0]],
                    [],
                    [],
                    [1.0, 2.0, 3.0, 180.0, 0.0, 0.0],
                )
            ),
            _paint_contact_command_path=MagicMock(
                side_effect=lambda path: [list(pose) for pose in path]
            ),
            _paint_start_staging_offset_pose=MagicMock(
                side_effect=lambda pose: list(pose)
            ),
            _paint_detach_staging_offset_pose=MagicMock(
                side_effect=lambda pose: list(pose)
            ),
        )
        execution_plan = SimpleNamespace(
            execution_jobs=[
                {
                    "pivot_source_path": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0]],
                    "pattern_type": "Workpiece",
                    "vel": 10.0,
                    "acc": 30.0,
                }
            ]
        )

        ok, msg, waypoints = PaintContactExecutor(owner).execute(execution_plan)

        self.assertTrue(ok, msg)
        self.assertEqual(waypoints, 1)
        self.assertEqual(events, ["preplan", "execute"])
        edge_cleanup.start_preplanning_during_paint.assert_called_once_with(
            execution_plan,
            started=ANY,
        )

    def test_simulation_config_exposes_plane_specific_indices_and_signs(self) -> None:
        xy = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="y",
            paint_side="negative",
            translation_direction="forward",
        )
        xz = PaintSimulationConfig(
            motion_plane="xz_y_ry",
            translation_axis="z",
            paint_side="positive",
            translation_direction="reverse",
        )

        self.assertEqual(xy.planar_axes, ("x", "y"))
        self.assertEqual(xy.planar_coordinate_indices, (0, 1))
        self.assertEqual(xy.source_planar_coordinate_indices, (0, 1))
        self.assertEqual(xy.orthogonal_position_index, 2)
        self.assertEqual(xy.rotation_index, 5)
        self.assertEqual(xy.orientation_overrides_deg, {})
        self.assertEqual(xy.valid_translation_axes, ("x", "y"))
        self.assertEqual(xy.paint_axis_offset_deg, 90.0)
        self.assertEqual(xy.side_sign, 1.0)
        self.assertEqual(xy.direction_sign, 1.0)

        self.assertEqual(xz.planar_axes, ("x", "z"))
        self.assertEqual(xz.planar_coordinate_indices, (0, 2))
        self.assertEqual(xz.orthogonal_position_index, 1)
        self.assertEqual(xz.rotation_index, 4)
        self.assertEqual(xz.orientation_overrides_deg, {})
        self.assertEqual(xz.paint_axis_offset_deg, 90.0)
        self.assertEqual(xz.side_sign, -1.0)
        self.assertEqual(xz.direction_sign, -1.0)

    def test_motion_plane_setup_outputs_complete_paint_plane_config(self) -> None:
        reference = Pose6D(10.0, 20.0, 30.0, 180.0, 0.0, 0.0)
        translation = Pose6D(-10.0, 20.0, 30.0, 180.0, 0.0, 0.0)
        rotation = Pose6D(10.0, 20.0, 30.0, 180.0, 0.0, 12.0)

        inference = infer_plane(reference, translation, rotation)
        config = inference.as_paint_plane_config(
            movement_group_id="Vertical Shaft",
            reference_pose=reference,
        )

        self.assertEqual(config["label"], "xy_z_rz")
        self.assertEqual(config["movement_group_id"], "Vertical Shaft")
        self.assertEqual(config["reference_pose"], reference.as_list())
        self.assertEqual(config["translation_axis"], "x")
        self.assertEqual(config["translation_direction"], "reverse")
        self.assertEqual(config["rotation_axis"], "rz")
        self.assertEqual(config["fixed_axis"], "z")
        self.assertEqual(config["planar_axes"], ["x", "y"])
        self.assertEqual(config["source_planar_coordinate_indices"], [0, 1])
        self.assertEqual(config["planar_coordinate_indices"], [0, 1])
        self.assertEqual(config["orthogonal_position_index"], 2)
        self.assertEqual(config["rotation_index"], 5)
        self.assertEqual(config["axis_offsets_deg"], {"x": 0.0, "y": 90.0})
        self.assertEqual(config["orientation_overrides_deg"], {})

    def test_normalize_contact_motion_config_preserves_valid_inputs_and_sanitizes_invalid_ones(self) -> None:
        normalized = _normalize_contact_motion_config(
            motion_plane="xz_y_ry",
            translation_axis="z",
            pivot_side="positive",
            translation_direction="reverse",
            apply_camera_to_tcp_for_pickup=True,
            camera_to_tcp_x_offset=12.5,
            camera_to_tcp_y_offset=-3.0,
        )
        fallback = _normalize_contact_motion_config(
            motion_plane="bad-plane",
            translation_axis="bad-axis",
            pivot_side="bad-side",
            translation_direction="bad-direction",
        )

        self.assertEqual(normalized.motion_plane, "xz_y_ry")
        self.assertEqual(normalized.translation_axis, "z")
        self.assertEqual(normalized.paint_side, "positive")
        self.assertEqual(normalized.translation_direction, "reverse")
        self.assertTrue(normalized.apply_camera_to_tcp_for_pickup)
        self.assertEqual(normalized.camera_to_tcp_x_offset, 12.5)
        self.assertEqual(normalized.camera_to_tcp_y_offset, -3.0)

        self.assertEqual(fallback.motion_plane, "xy_z_rz")
        self.assertEqual(fallback.translation_axis, "x")
        self.assertEqual(fallback.paint_side, "negative")
        self.assertEqual(fallback.translation_direction, "forward")


class TestPaintPickupPlanner(unittest.TestCase):
    def test_camera_to_tcp_delta_accounts_for_rotation_from_reference(self) -> None:
        dx, dy = _camera_to_tcp_delta(10.0, 0.0, current_rz=90.0, reference_rz=0.0)

        self.assertAlmostEqual(dx, -10.0, places=6)
        self.assertAlmostEqual(dy, 10.0, places=6)


if __name__ == "__main__":
    unittest.main()
