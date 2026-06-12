from __future__ import annotations

import unittest

from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintProcessConfig,
    PaintSimulationConfig,
)
from src.robot_systems.paint.processes.paint.execute.workpiece_path_executor import (
    _camera_to_tcp_delta,
    _normalize_pivot_config,
)


class TestPaintProcessConfig(unittest.TestCase):
    def test_process_config_derived_properties_follow_motion_plane(self) -> None:
        default_config = PaintProcessConfig()
        xy_config = PaintProcessConfig(pivot_motion_plane="xy_z_rz")

        self.assertEqual(PAINT_PROCESS_CONFIG.paint_base_group_id, "PAINTING_NEW")
        self.assertEqual(default_config.paint_base_group_id, "PAINTING_NEW")
        self.assertEqual(default_config.pickup_base_group_id, "PAINTING")
        self.assertEqual(default_config.pivot_side, "positive")
        self.assertEqual(xy_config.paint_base_group_id, "PAINTING")
        self.assertEqual(xy_config.pivot_side, "positive")

    def test_process_config_exposes_pickup_defaults_used_by_executor(self) -> None:
        default_config = PaintProcessConfig()

        self.assertEqual(default_config.pickup_default_z_mm, 300.0)
        self.assertEqual(default_config.pickup_default_vel_percent, 20.0)
        self.assertEqual(default_config.pickup_default_acc_percent, 50.0)
        self.assertEqual(default_config.pickup_approach_vel_percent, 10.0)
        self.assertEqual(default_config.pickup_approach_acc_percent, 30.0)
        self.assertEqual(default_config.pickup_descend_vel_percent, 60.0)
        self.assertEqual(default_config.pickup_descend_acc_percent, 20.0)
        self.assertEqual(default_config.pickup_lift_align_vel_percent, 20.0)
        self.assertEqual(default_config.pickup_lift_align_acc_percent, 70.0)
        self.assertEqual(default_config.pickup_change_plane_vel_percent, 20.0)
        self.assertEqual(default_config.pickup_change_plane_acc_percent, 50.0)
        self.assertEqual(default_config.pickup_stage_transition_vel_percent, 20.0)
        self.assertEqual(default_config.pickup_stage_transition_acc_percent, 50.0)
        self.assertEqual(default_config.pickup_first_contact_vel_percent, 20.0)
        self.assertEqual(default_config.pickup_first_contact_acc_percent, 70.0)
        self.assertEqual(default_config.pickup_restore_orientation_z_lift_mm, 10.0)
        self.assertEqual(default_config.pickup_approach_offset_mm, 100.0)
        self.assertEqual(default_config.pickup_contact_offset_mm, 2.0)

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
        self.assertEqual(xz.contact_heading_offset_deg, 180.0)
        self.assertEqual(xz.paint_axis_offset_deg, 90.0)
        self.assertEqual(xz.side_sign, -1.0)
        self.assertEqual(xz.direction_sign, -1.0)

    def test_normalize_pivot_config_preserves_valid_inputs_and_sanitizes_invalid_ones(self) -> None:
        normalized = _normalize_pivot_config(
            motion_plane="xz_y_ry",
            translation_axis="z",
            pivot_side="positive",
            translation_direction="reverse",
            apply_camera_to_tcp_for_pickup=True,
            camera_to_tcp_x_offset=12.5,
            camera_to_tcp_y_offset=-3.0,
        )
        fallback = _normalize_pivot_config(
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
