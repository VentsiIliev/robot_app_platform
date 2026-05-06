from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import numpy as np

from src.robot_systems.paint.processes.paint.config import (
    PAINT_PROCESS_CONFIG,
    PaintProcessConfig,
    PaintSimulationConfig,
)
from src.robot_systems.paint.processes.paint.dxf_image_placement import (
    estimate_local_image_basis,
    map_raw_workpiece_mm_to_image,
)
from src.robot_systems.paint.processes.paint.pickup_planner import _camera_to_tcp_delta


class TestPaintProcessConfig(unittest.TestCase):
    def test_process_config_derived_properties_follow_motion_plane(self) -> None:
        default_config = PaintProcessConfig()
        xy_config = PaintProcessConfig(pivot_motion_plane="xy_z_rz")

        self.assertEqual(PAINT_PROCESS_CONFIG.paint_base_group_id, "PAINTING_NEW")
        self.assertEqual(default_config.paint_base_group_id, "PAINTING_NEW")
        self.assertEqual(default_config.pickup_base_group_id, "PAINTING")
        self.assertEqual(default_config.pivot_side, "positive")
        self.assertEqual(xy_config.paint_base_group_id, "PAINTING")
        self.assertEqual(xy_config.pivot_side, "negative")

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
        self.assertEqual(xz.orientation_overrides_deg, {"rx": 90.0})
        self.assertEqual(xz.paint_axis_offset_deg, 90.0)
        self.assertEqual(xz.side_sign, -1.0)
        self.assertEqual(xz.direction_sign, -1.0)


class TestPaintDxfImagePlacement(unittest.TestCase):
    def test_estimate_local_image_basis_uses_transformer_inverse_mapping(self) -> None:
        transformer = MagicMock()
        transformer.is_available.return_value = True
        transformer.transform.return_value = (10.0, 20.0)

        def inverse_transform(x: float, y: float) -> tuple[float, float]:
            return (x - 10.0, y - 20.0)

        transformer.inverse_transform.side_effect = inverse_transform

        basis = estimate_local_image_basis(transformer, 100.0, 60.0)

        self.assertIsNotNone(basis)
        origin, basis_x, basis_y = basis
        np.testing.assert_allclose(origin, np.array([0.0, 0.0]))
        np.testing.assert_allclose(basis_x, np.array([1.0, 0.0]))
        np.testing.assert_allclose(basis_y, np.array([0.0, 1.0]))

    def test_estimate_local_image_basis_returns_none_when_unavailable_or_invalid(self) -> None:
        unavailable = MagicMock()
        unavailable.is_available.return_value = False
        self.assertIsNone(estimate_local_image_basis(unavailable, 10.0, 10.0))

        broken = MagicMock()
        broken.is_available.return_value = True
        broken.transform.side_effect = RuntimeError("boom")
        self.assertIsNone(estimate_local_image_basis(broken, 10.0, 10.0))

    def test_map_raw_workpiece_mm_to_image_recenters_contours_and_spray_segments(self) -> None:
        raw = {
            "contour": [[[10.0, 20.0]], [[14.0, 24.0]]],
            "sprayPattern": {
                "Contour": [{"contour": [[[10.0, 20.0]], [[14.0, 24.0]]]}],
                "Fill": [{"contour": [[[12.0, 22.0]]]}],
            },
        }
        transformer = MagicMock()
        transformer.is_available.return_value = False

        placed = map_raw_workpiece_mm_to_image(raw, 100.0, 50.0, transformer)

        self.assertEqual(raw["contour"][0][0], [10.0, 20.0])
        np.testing.assert_allclose(placed["contour"][0][0], [48.0, 23.0])
        np.testing.assert_allclose(placed["contour"][1][0], [52.0, 27.0])
        np.testing.assert_allclose(
            placed["sprayPattern"]["Contour"][0]["contour"][0][0],
            [48.0, 23.0],
        )
        np.testing.assert_allclose(
            placed["sprayPattern"]["Fill"][0]["contour"][0][0],
            [50.0, 25.0],
        )

    def test_map_raw_workpiece_mm_to_image_returns_copy_when_no_points_exist(self) -> None:
        raw = {"contour": []}

        placed = map_raw_workpiece_mm_to_image(raw, 100.0, 50.0, transformer=None)

        self.assertEqual(placed, raw)
        self.assertIsNot(placed, raw)


class TestPaintPickupPlanner(unittest.TestCase):
    def test_camera_to_tcp_delta_accounts_for_rotation_from_reference(self) -> None:
        dx, dy = _camera_to_tcp_delta(10.0, 0.0, current_rz=90.0, reference_rz=0.0)

        self.assertAlmostEqual(dx, -10.0, places=6)
        self.assertAlmostEqual(dy, 10.0, places=6)


if __name__ == "__main__":
    unittest.main()
