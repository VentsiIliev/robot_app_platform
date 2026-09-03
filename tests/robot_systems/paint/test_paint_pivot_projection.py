from __future__ import annotations

import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.config import PaintSimulationConfig
from src.robot_systems.paint.processes.paint.plan.paint_contact_motion import (
    project_paint_motion_geometry_continuous,
    rebase_projected_paint_path_to_zero_start_rz,
)


class TestPaintPivotProjection(unittest.TestCase):
    def test_closed_contour_overlap_adds_exact_arc_length(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="x",
            paint_side="negative",
            translation_direction="forward",
            closed_contour_overlap_mm=10.0,
        )
        path = [
            [0.0, 0.0, 5.0, 0.0, 0.0, 0.0],
            [20.0, 0.0, 5.0, 0.0, 0.0, 0.0],
            [20.0, 20.0, 5.0, 0.0, 0.0, 0.0],
            [0.0, 20.0, 5.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 5.0, 0.0, 0.0, 0.0],
        ]

        projected, _, diagnostics = project_paint_motion_geometry_continuous(
            path,
            [100.0, 200.0, 300.0, 0.0, 0.0, 0.0],
            config,
            anchor_xy=(10.0, 10.0),
        )

        travelled_mm = sum(float(entry["segment_length"]) for entry in diagnostics)
        self.assertAlmostEqual(travelled_mm, 90.0, places=6)
        self.assertGreater(len(projected), len(path))
        self.assertTrue(all(float(entry["contact_error_mm"]) <= 1e-6 for entry in diagnostics))

    def test_closed_contour_overlap_rejects_a_second_full_lap(self) -> None:
        config = PaintSimulationConfig(closed_contour_overlap_mm=40.0)
        path = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [10.0, 10.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 10.0, 0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        ]

        with self.assertRaisesRegex(ValueError, "must be smaller than"):
            project_paint_motion_geometry_continuous(
                path,
                [100.0, 200.0, 300.0, 0.0, 0.0, 0.0],
                config,
            )

    def test_continuous_projection_keeps_each_arc_sample_on_pivot(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="x",
            paint_side="negative",
            translation_direction="forward",
        )
        path = []
        for angle_deg in np.linspace(0.0, 90.0, 91):
            angle_rad = np.radians(angle_deg)
            path.append([
                float(20.0 * np.cos(angle_rad)),
                float(20.0 * np.sin(angle_rad)),
                5.0,
                1.0,
                2.0,
                3.0,
            ])
        pivot_pose = [100.0, 200.0, 300.0, 10.0, 20.0, 0.0]

        projected, snapshots, diagnostics = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            config,
            anchor_xy=(0.0, 0.0),
        )

        self.assertEqual(len(projected), len(snapshots))
        self.assertEqual(len(projected), len(diagnostics))
        self.assertGreaterEqual(len(projected), len(path))
        for entry in diagnostics:
            self.assertAlmostEqual(float(entry["contact_error_mm"]), 0.0, places=6)
        rotation_deltas = [
            abs(float(entry["rotation_delta_applied"]))
            for entry in diagnostics[1:]
        ]
        self.assertTrue(all(delta <= 1.0 + 1e-6 for delta in rotation_deltas))

    def test_continuous_projection_splits_corner_rotation_to_one_degree_steps(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="x",
            paint_side="negative",
            translation_direction="forward",
        )
        path = [
            [0.0, 0.0, 5.0, 1.0, 2.0, 3.0],
            [10.0, 0.0, 5.0, 1.0, 2.0, 3.0],
            [10.0, 10.0, 5.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [100.0, 200.0, 300.0, 10.0, 20.0, 0.0]

        projected, _, diagnostics = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            config,
            anchor_xy=(5.0, 5.0),
        )

        self.assertGreater(len(projected), len(path))
        for entry in diagnostics:
            self.assertAlmostEqual(float(entry["contact_error_mm"]), 0.0, places=6)
        self.assertAlmostEqual(float(diagnostics[-1]["geometry_rotation"]), 90.0, places=6)
        rotation_deltas = [
            abs(float(entry["rotation_delta_applied"]))
            for entry in diagnostics[1:]
        ]
        self.assertTrue(all(delta <= 1.0 + 1e-6 for delta in rotation_deltas))

    def test_continuous_projection_applies_xz_rotation_direction_inside_projection(self) -> None:
        normal_config = PaintSimulationConfig(
            motion_plane="xz_y_ry",
            translation_axis="x",
            paint_side="positive",
            translation_direction="reverse",
            rotation_direction_sign=1.0,
        )
        mirrored_config = PaintSimulationConfig(
            motion_plane="xz_y_ry",
            translation_axis="x",
            paint_side="positive",
            translation_direction="reverse",
            rotation_direction_sign=-1.0,
        )
        path = [
            [0.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [10.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [10.0, 10.0, 0.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [100.0, 200.0, 300.0, -91.0, 0.0, -0.05]

        normal_projected, _, _ = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            normal_config,
            anchor_xy=(5.0, 5.0),
        )
        projected, _, diagnostics = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            mirrored_config,
            anchor_xy=(5.0, 5.0),
        )

        self.assertGreaterEqual(len(projected), len(path))
        self.assertLess(normal_projected[-1][4], normal_projected[0][4])
        self.assertGreater(projected[-1][4], projected[0][4])
        self.assertAlmostEqual(
            float(diagnostics[-1]["geometry_rotation"]),
            -90.0,
            places=6,
        )
        self.assertAlmostEqual(
            float(diagnostics[-1]["command_relative_rotation"]),
            90.0,
            places=6,
        )
        for entry in diagnostics:
            self.assertAlmostEqual(float(entry["contact_error_mm"]), 0.0, places=6)
        rotation_deltas = [
            abs(float(entry["rotation_delta_applied"]))
            for entry in diagnostics[1:]
        ]
        self.assertTrue(all(delta <= 1.0 + 1e-6 for delta in rotation_deltas))

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

    def test_project_paint_motion_geometry_continuous_projects_simple_xy_path_around_pivot(self) -> None:
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

        projected, snapshots, diagnostics = project_paint_motion_geometry_continuous(path, pivot_pose, config)

        self.assertEqual(len(projected), 2)
        self.assertEqual(len(snapshots), 2)
        self.assertEqual(len(diagnostics), 2)
        np.testing.assert_allclose(projected[0], [95.0, 200.0, 300.0, 10.0, 20.0, 180.0], atol=1e-6)
        np.testing.assert_allclose(projected[1], [105.0, 200.0, 300.0, 10.0, 20.0, 180.0], atol=1e-6)
        self.assertEqual(snapshots[0].shape, (0, 2))
        self.assertEqual(snapshots[1].shape, (0, 2))
        self.assertEqual(diagnostics[0]["rotation_delta_raw"], 180.0)
        self.assertEqual(diagnostics[0]["rotation_delta_applied"], 0.0)
        self.assertEqual(diagnostics[1]["rotation_delta_applied"], 0.0)

    def test_project_paint_motion_geometry_continuous_uses_explicit_tcp_anchor_for_pose_xy(self) -> None:
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

        projected, snapshots, _ = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            config,
            anchor_xy=(2.0, 0.0),
        )

        np.testing.assert_allclose(projected[0][:2], [98.0, 200.0], atol=1e-6)
        np.testing.assert_allclose(projected[1][:2], [108.0, 200.0], atol=1e-6)
        self.assertEqual(snapshots[0].shape, (0, 2))

    def test_project_paint_motion_geometry_continuous_prefers_long_initial_translation_run(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xy_z_rz",
            translation_axis="x",
            paint_side="negative",
            translation_direction="reverse",
        )
        path = [
            [-100.0, 10.0, 5.0, 1.0, 2.0, 3.0],
            [-1.0, 10.0, 5.0, 1.0, 2.0, 3.0],
            [0.0, 10.0, 5.0, 1.0, 2.0, 3.0],
            [0.0, 0.0, 5.0, 1.0, 2.0, 3.0],
            [-100.0, 0.0, 5.0, 1.0, 2.0, 3.0],
            [-100.0, 10.0, 5.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [100.0, 200.0, 300.0, 10.0, 20.0, 0.0]

        _, snapshots, diagnostics = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            config,
            anchor_xy=(-1.0, 10.0),
        )

        self.assertEqual(snapshots[0].shape, (0, 2))
        self.assertAlmostEqual(float(diagnostics[1]["rotation_delta_applied"]), 0.0, places=6)

    def test_project_paint_motion_geometry_continuous_applies_source_rotation_about_tcp_anchor(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xz_y_ry",
            translation_axis="x",
            paint_side="positive",
            translation_direction="forward",
        )
        path = [
            [-20.0, 34.0, 5.0, 1.0, 2.0, 3.0],
            [-65.0, 29.0, 5.0, 1.0, 2.0, 3.0],
            [-60.0, -5.0, 5.0, 1.0, 2.0, 3.0],
            [25.0, -12.0, 5.0, 1.0, 2.0, 3.0],
            [30.0, 30.0, 5.0, 1.0, 2.0, 3.0],
            [-20.0, 34.0, 5.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [-80.0, 200.0, 335.0, -91.0, 0.0, -0.05]

        unrotated, _, _ = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            config,
            anchor_xy=(-10.0, 31.0),
        )
        rotated, snapshots, _ = project_paint_motion_geometry_continuous(
            path,
            pivot_pose,
            config,
            anchor_xy=(-10.0, 31.0),
            source_rotation_deg=-12.0,
        )

        self.assertNotAlmostEqual(unrotated[0][4], rotated[0][4], places=3)
        self.assertEqual(snapshots[0].shape, (0, 2))

    def test_project_paint_motion_geometry_continuous_xz_plane_uses_opposed_contact_heading(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xz_y_ry",
            translation_axis="x",
            paint_side="positive",
            translation_direction="forward",
        )
        path = [
            [0.0, 0.0, 5.0, 1.0, 2.0, 3.0],
            [10.0, 0.0, 5.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [100.0, 200.0, 300.0, -91.0, 0.0, -0.05]

        projected, snapshots, diagnostics = project_paint_motion_geometry_continuous(path, pivot_pose, config)

        np.testing.assert_allclose(projected[0], [95.0, 200.0, 300.0, -91.0, 180.0, -0.05], atol=1e-6)
        self.assertEqual(snapshots[0].shape, (0, 2))
        self.assertEqual(diagnostics[0]["rotation_delta_raw"], 180.0)
        self.assertEqual(diagnostics[0]["rotation_delta_applied"], 0.0)

    def test_project_paint_motion_geometry_continuous_for_single_point_returns_snapshot_without_diagnostics(self) -> None:
        config = PaintSimulationConfig(motion_plane="xz_y_ry")
        path = [[7.0, 9.0, 11.0, 1.0, 2.0, 3.0]]
        pivot_pose = [100.0, 200.0, 300.0, 10.0, 20.0, 30.0]

        projected, snapshots, diagnostics = project_paint_motion_geometry_continuous(path, pivot_pose, config)

        self.assertEqual(projected, [[100.0, 200.0, 300.0, 10.0, 20.0, 30.0]])
        self.assertEqual(snapshots[0].shape, (0, 2))
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0]["rotation_delta_applied"], 0.0)

    def test_project_paint_motion_geometry_continuous_does_not_schedule_rotation_on_straight_lead_in(self) -> None:
        config = PaintSimulationConfig(
            motion_plane="xz_y_ry",
            translation_axis="x",
            paint_side="positive",
            translation_direction="forward",
        )
        path = [
            [0.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [10.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [20.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [30.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [40.0, 0.0, 0.0, 1.0, 2.0, 3.0],
            [50.0, -10.0, 0.0, 1.0, 2.0, 3.0],
            [50.0, -20.0, 0.0, 1.0, 2.0, 3.0],
            [40.0, -20.0, 0.0, 1.0, 2.0, 3.0],
            [30.0, -20.0, 0.0, 1.0, 2.0, 3.0],
            [20.0, -20.0, 0.0, 1.0, 2.0, 3.0],
            [10.0, -20.0, 0.0, 1.0, 2.0, 3.0],
            [0.0, -20.0, 0.0, 1.0, 2.0, 3.0],
            [0.0, -10.0, 0.0, 1.0, 2.0, 3.0],
            [0.0, 0.0, 0.0, 1.0, 2.0, 3.0],
        ]
        pivot_pose = [100.0, 200.0, 300.0, -91.0, 0.0, -0.05]

        _, _, diagnostics = project_paint_motion_geometry_continuous(path, pivot_pose, config)

        straight_with_scheduled_rotation = [
            entry for entry in diagnostics
            if float(entry.get("segment_length", 0.0)) > 1e-9
            and abs(float(entry.get("rotation_delta_raw", 0.0))) < 1e-6
            and abs(float(entry.get("rotation_delta_applied", 0.0))) > 1e-6
        ]
        self.assertEqual(straight_with_scheduled_rotation, [])


if __name__ == "__main__":
    unittest.main()
