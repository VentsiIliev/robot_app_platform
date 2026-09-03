from __future__ import annotations

import unittest

import cv2
import numpy as np

from scripts.paint_shaft_alignment.orientation import (
    ComparingOrientationStrategy,
    CornerEdgeOrientationStrategy,
    SolvePnPOrientationStrategy,
)


class MarkerOrientationStrategyTests(unittest.TestCase):
    def test_corner_edge_strategy_preserves_current_convention(self):
        strategy = CornerEdgeOrientationStrategy()

        angle = strategy.orientation_deg(((10.0, 10.0), (20.0, 20.0), (10.0, 30.0), (0.0, 20.0)))

        self.assertAlmostEqual(45.0, angle)

    def test_solve_pnp_recovers_camera_frame_yaw(self):
        camera_matrix = np.array(
            [[900.0, 0.0, 640.0], [0.0, 900.0, 360.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        distortion = np.zeros((5, 1), dtype=np.float64)
        marker_size = 10.0
        half = marker_size / 2.0
        object_points = np.array(
            [[-half, half, 0.0], [half, half, 0.0], [half, -half, 0.0], [-half, -half, 0.0]],
            dtype=np.float64,
        )
        yaw_deg = 30.0
        yaw = np.radians(yaw_deg)
        rotation = np.array(
            [[np.cos(yaw), -np.sin(yaw), 0.0], [np.sin(yaw), np.cos(yaw), 0.0], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
        rvec, _ = cv2.Rodrigues(rotation)
        image_points, _ = cv2.projectPoints(
            object_points,
            rvec,
            np.array([[0.0], [0.0], [250.0]]),
            camera_matrix,
            distortion,
        )
        strategy = SolvePnPOrientationStrategy(
            marker_size_mm=marker_size,
            camera_matrix=camera_matrix,
            distortion_coefficients=distortion,
        )

        result = strategy.orientation_deg(image_points.reshape(4, 2))

        self.assertAlmostEqual(yaw_deg, result, places=3)

        estimate = strategy.estimate(image_points.reshape(4, 2))
        diagnostics = dict(estimate.diagnostics)
        self.assertAlmostEqual(0.0, diagnostics["solve_pnp.rx_deg"], places=3)
        self.assertAlmostEqual(0.0, diagnostics["solve_pnp.ry_deg"], places=3)
        self.assertAlmostEqual(250.0, diagnostics["solve_pnp.z_mm"], places=3)
        self.assertLess(diagnostics["solve_pnp.reprojection_error_px"], 1e-6)

    def test_comparison_uses_same_corners_and_selected_primary(self):
        class _Strategy:
            def __init__(self, name, value):
                self.name = name
                self.value = value
                self.received = None

            def estimate(self, corners):
                from scripts.paint_shaft_alignment.orientation import MarkerOrientationEstimate

                self.received = tuple(corners)
                return MarkerOrientationEstimate(self.value, ((self.name, self.value),))

        corners = ((1.0, 2.0), (3.0, 2.0), (3.0, 4.0), (1.0, 4.0))
        edge = _Strategy("corner_edge", 10.0)
        pnp = _Strategy("solve_pnp", 12.0)
        strategy = ComparingOrientationStrategy((edge, pnp), primary_name="solve_pnp")

        result = strategy.estimate(corners)

        self.assertEqual(12.0, result.primary_deg)
        self.assertEqual((("corner_edge", 10.0), ("solve_pnp", 12.0)), result.samples)
        self.assertEqual(corners, edge.received)
        self.assertEqual(corners, pnp.received)


if __name__ == "__main__":
    unittest.main()
