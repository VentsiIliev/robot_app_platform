import math
import unittest

import numpy as np

from src.engine.robot.calibration.tool_tcp_calibration_data import ToolTcpSample
from src.engine.robot.calibration.tool_tcp_pivot_solver import solve_tool_tcp_pivot


def _rotation_matrix_xyz_degrees(rx: float, ry: float, rz: float) -> np.ndarray:
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cy, sy = math.cos(math.radians(ry)), math.sin(math.radians(ry))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    rx_m = np.asarray([[1.0, 0.0, 0.0], [0.0, cx, -sx], [0.0, sx, cx]], dtype=np.float64)
    ry_m = np.asarray([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]], dtype=np.float64)
    rz_m = np.asarray([[cz, -sz, 0.0], [sz, cz, 0.0], [0.0, 0.0, 1.0]], dtype=np.float64)
    return rz_m @ ry_m @ rx_m


def _sample_for(
    tool_offset_xyz: np.ndarray,
    pivot_point: np.ndarray,
    orientation: tuple[float, float, float],
    translation_noise: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> ToolTcpSample:
    rotation = _rotation_matrix_xyz_degrees(*orientation)
    translation = pivot_point - rotation @ tool_offset_xyz + np.asarray(translation_noise, dtype=np.float64)
    return ToolTcpSample.from_pose([*translation.tolist(), *orientation])


class TestToolTcpPivotSolver(unittest.TestCase):
    def test_solves_known_offset_from_noise_free_samples(self):
        tool_offset = np.asarray([12.5, -8.0, 93.25], dtype=np.float64)
        pivot = np.asarray([300.0, -120.0, 450.0], dtype=np.float64)
        samples = [
            _sample_for(tool_offset, pivot, orientation)
            for orientation in [
                (0.0, 0.0, 0.0),
                (20.0, 0.0, 0.0),
                (-20.0, 10.0, 0.0),
                (15.0, -15.0, 30.0),
                (-10.0, 20.0, -35.0),
                (30.0, -10.0, 45.0),
                (-25.0, -20.0, 60.0),
            ]
        ]

        result = solve_tool_tcp_pivot(samples)

        np.testing.assert_allclose(result.tool_offset[:3], tool_offset, atol=1e-9)
        np.testing.assert_allclose(result.tool_offset[3:], [0.0, 0.0, 0.0], atol=1e-12)
        np.testing.assert_allclose(result.pivot_point, pivot, atol=1e-9)
        self.assertLess(result.residual_rms_mm, 1e-9)
        self.assertLess(result.residual_max_mm, 1e-9)
        self.assertEqual(result.sample_count, len(samples))

    def test_reports_residuals_for_noisy_samples(self):
        tool_offset = np.asarray([40.0, 15.0, 110.0], dtype=np.float64)
        pivot = np.asarray([100.0, 200.0, 300.0], dtype=np.float64)
        orientations = [
            (0.0, 0.0, 0.0),
            (15.0, 0.0, 0.0),
            (-15.0, 10.0, 5.0),
            (10.0, -20.0, 30.0),
            (-25.0, 5.0, -30.0),
            (30.0, -15.0, 45.0),
            (-30.0, -20.0, 60.0),
            (5.0, 25.0, -45.0),
        ]
        noises = [
            (0.05, -0.03, 0.02),
            (-0.02, 0.04, -0.01),
            (0.03, 0.01, -0.04),
            (-0.04, -0.02, 0.03),
            (0.01, -0.05, 0.01),
            (0.02, 0.03, -0.02),
            (-0.03, 0.02, 0.05),
            (0.04, -0.01, -0.03),
        ]
        samples = [
            _sample_for(tool_offset, pivot, orientation, noise)
            for orientation, noise in zip(orientations, noises)
        ]

        result = solve_tool_tcp_pivot(samples)

        np.testing.assert_allclose(result.tool_offset[:3], tool_offset, atol=0.25)
        self.assertGreater(result.residual_rms_mm, 0.0)
        self.assertLess(result.residual_rms_mm, 0.15)
        self.assertLess(result.residual_max_mm, 0.25)

    def test_rejects_insufficient_samples(self):
        samples = [
            _sample_for(
                np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
                np.asarray([10.0, 20.0, 30.0], dtype=np.float64),
                (float(index), 0.0, 0.0),
            )
            for index in range(5)
        ]

        with self.assertRaisesRegex(ValueError, "at least 6 samples"):
            solve_tool_tcp_pivot(samples)

    def test_rejects_degenerate_orientation_set(self):
        samples = [
            _sample_for(
                np.asarray([1.0, 2.0, 3.0], dtype=np.float64),
                np.asarray([10.0, 20.0, 30.0], dtype=np.float64),
                (0.0, 0.0, 0.0),
            )
            for _ in range(6)
        ]

        with self.assertRaisesRegex(ValueError, "degenerate"):
            solve_tool_tcp_pivot(samples)

    def test_rejects_non_finite_pose_values(self):
        samples = [
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0, 10.0, 0.0, 0.0],
            [2.0, 0.0, 0.0, -10.0, 0.0, 0.0],
            [3.0, 0.0, 0.0, 0.0, 10.0, 0.0],
            [4.0, 0.0, 0.0, 0.0, -10.0, 0.0],
            [math.nan, 0.0, 0.0, 0.0, 0.0, 10.0],
        ]

        with self.assertRaisesRegex(ValueError, "finite"):
            solve_tool_tcp_pivot(samples)


if __name__ == "__main__":
    unittest.main()
