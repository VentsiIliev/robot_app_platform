from __future__ import annotations

import unittest

from src.robot_systems.paint.processes.paint.execution_plane import (
    get_execution_plane_strategy,
)


class TestPaintExecutionPlaneStrategies(unittest.TestCase):
    def test_xy_strategy_uses_y_offset_rz_alignment_and_no_preflight_or_flip(self) -> None:
        strategy = get_execution_plane_strategy("xy_z_rz")
        pivot_path = [[0.0, 0.0, 0.0, 0.0, 1.0, 10.0]]

        align_rotation = strategy.compute_pickup_align_rotation(
            pickup_rz=33.0,
            pickup_ry=5.0,
            first_pivot_pose=[100.0, 200.0, 300.0, 1.0, 2.0, 44.0],
            paint_pivot_pose=[10.0, 20.0, 30.0, 4.0, 5.0, 6.0],
        )
        flipped = strategy.maybe_flip_execution_rotation_direction(
            pivot_path=[list(pose) for pose in pivot_path],
            enabled=True,
        )

        self.assertEqual(strategy.motion_plane, "xy_z_rz")
        self.assertEqual(strategy.pivot_offset_position_index, 1)
        self.assertFalse(strategy.requires_reachability_preflight)
        self.assertEqual(strategy.rotation_axis_label, "RZ")
        self.assertEqual(align_rotation, 44.0)
        self.assertEqual(flipped, pivot_path)

    def test_xz_strategy_uses_z_offset_ry_alignment_and_optional_flip(self) -> None:
        strategy = get_execution_plane_strategy("xz_y_ry")
        pivot_path = [
            [0.0, 0.0, 0.0, 0.0, 10.0, 20.0],
            [1.0, 2.0, 3.0, 4.0, 12.0, 30.0],
        ]

        align_rotation = strategy.compute_pickup_align_rotation(
            pickup_rz=30.0,
            pickup_ry=5.0,
            first_pivot_pose=[100.0, 200.0, 300.0, 1.0, 20.0, 44.0],
            paint_pivot_pose=[10.0, 20.0, 30.0, 4.0, 10.0, 6.0],
        )
        flipped = strategy.maybe_flip_execution_rotation_direction(
            pivot_path=[list(pose) for pose in pivot_path],
            enabled=True,
        )

        self.assertEqual(strategy.motion_plane, "xz_y_ry")
        self.assertEqual(strategy.pivot_offset_position_index, 2)
        self.assertTrue(strategy.requires_reachability_preflight)
        self.assertEqual(strategy.rotation_axis_label, "RY")
        self.assertEqual(align_rotation, 40.0)
        self.assertEqual(flipped[0][4], 10.0)
        self.assertEqual(flipped[1][4], 8.0)


if __name__ == "__main__":
    unittest.main()
