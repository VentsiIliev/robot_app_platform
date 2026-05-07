from __future__ import annotations

import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.pivot_projection import (
    project_paint_motion_geometry,
    rebase_projected_paint_path_to_zero_start_rz,
)


class TestPaintPivotProjection(unittest.TestCase):
    def test_rebase_projected_paint_path_to_zero_start_rotation_uses_active_rotation_index(self) -> None:
        config = PaintSimulationConfig(motion_plane="xy_z_rz")
        path = [
            [1.0, 2.0, 3.0, 10.0, 20.0, 45.0],
            [4.0, 5.0, 6.0, 10.0, 20.0, 60.0],
        ]

        rebased = rebase_projected_paint_path_to_zero_start_rz(path, config)

        self.assertEqual(path[0][5], 45.0)
        self.assertEqual(rebased[0][5], 0.0)
        self.assertEqual(rebased[1][5], 15.0)

    def test_project_paint_motion_geometry_projects_simple_xy_path_around_pivot(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="x",
            paint_side="negative",
            translation_direction="forward",
        )
        path = [
            [0.0, 0.0, 5.0, 1.0, 2.0, 3.0],
            [10.0, 0.0, 5.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [100.0, 200.0, 300.0, 10.0, 20.0, 0.0]

        projected, snapshots, diagnostics = project_paint_motion_geometry(path, pivot_pose, config)

        self.assertEqual(len(projected), 2)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(len(diagnostics), 2)
        np.testing.assert_allclose(projected[0], [95.0, 200.0, 300.0, 10.0, 20.0, 180.0], atol=1e-6)
        np.testing.assert_allclose(projected[1], [105.0, 200.0, 300.0, 10.0, 20.0, 180.0], atol=1e-6)
        np.testing.assert_allclose(snapshots[0], np.array([[100.0, 200.0], [90.0, 200.0]]), atol=1e-6)
        np.testing.assert_allclose(snapshots[1], np.array([[110.0, 200.0], [100.0, 200.0]]), atol=1e-6)
        self.assertEqual(diagnostics[0]["rotation_delta_applied"], 180.0)
        self.assertEqual(diagnostics[1]["rotation_delta_applied"], 0.0)

    def test_project_paint_motion_geometry_for_single_point_returns_snapshot_without_diagnostics(self) -> None:
        config = PaintSimulationConfig(motion_plane="xz_y_ry")
        path = [[7.0, 9.0, 11.0, 1.0, 2.0, 3.0]]
        pivot_pose = [100.0, 200.0, 300.0, 10.0, 20.0, 30.0]

        projected, snapshots, diagnostics = project_paint_motion_geometry(path, pivot_pose, config)

        self.assertEqual(projected, [path[0]])
        np.testing.assert_allclose(snapshots[0], np.array([[7.0, 9.0]]), atol=1e-6)
        self.assertEqual(diagnostics, [])


if __name__ == "__main__":
    unittest.main()
