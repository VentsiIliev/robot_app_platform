from __future__ import annotations

import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
    PaintContourInterpolation,
    PaintContourInterpolationConfig,
    remove_local_hairpin_reversals_xy,
    resample_contour_xy,
)


def _pose_path_from_xy(xy_points: list[tuple[float, float]]) -> list[list[float]]:
    return [[float(x), float(y), 0.0, 0.0, 0.0, 0.0] for x, y in xy_points]


def _max_xy_spacing(path: list[list[float]]) -> float:
    points = np.asarray(path, dtype=float)[:, :2]
    if len(points) < 2:
        return 0.0
    return float(np.max(np.linalg.norm(np.diff(points, axis=0), axis=1)))


def _point_to_polyline_distances(points: np.ndarray, polyline: np.ndarray) -> np.ndarray:
    pts = np.asarray(points, dtype=np.float64).reshape(-1, 2)
    line = np.asarray(polyline, dtype=np.float64).reshape(-1, 2)
    starts = line
    ends = np.roll(line, -1, axis=0)
    distances = np.full(len(pts), np.inf, dtype=np.float64)
    for start, end in zip(starts, ends):
        segment = end - start
        length_sq = float(np.dot(segment, segment))
        if length_sq <= 1e-12:
            candidate = np.linalg.norm(pts - start, axis=1)
        else:
            t = np.clip(((pts - start) @ segment) / length_sq, 0.0, 1.0)
            projection = start + t[:, None] * segment
            candidate = np.linalg.norm(pts - projection, axis=1)
        distances = np.minimum(distances, candidate)
    return distances


class TestPaintContourInterpolation(unittest.TestCase):
    def test_removes_logged_near_retrace_hairpin(self) -> None:
        points = np.asarray(
            [
                [186.8, 250.2],
                [187.7492829, 251.132285472],
                [187.218974672, 252.115435842],
                [187.723003726, 251.141915909],
                [188.6, 250.3],
            ],
            dtype=float,
        )

        cleaned = remove_local_hairpin_reversals_xy(
            points,
            spacing=1.0,
            closed=False,
        )

        self.assertEqual(len(cleaned), 4)
        self.assertFalse(np.any(np.all(np.isclose(cleaned, points[2]), axis=1)))
        vectors = np.diff(cleaned, axis=0)
        unit = vectors / np.linalg.norm(vectors, axis=1)[:, None]
        self.assertTrue(np.all(np.sum(unit[:-1] * unit[1:], axis=1) > np.cos(np.radians(170.0))))

    def test_hairpin_cleanup_preserves_legitimate_sharp_corner(self) -> None:
        points = np.asarray(
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [2.0, 1.0]],
            dtype=float,
        )

        cleaned = remove_local_hairpin_reversals_xy(
            points,
            spacing=1.0,
            closed=False,
        )

        np.testing.assert_allclose(cleaned, points)

    def test_preserves_float_coordinates(self) -> None:
        raw = _pose_path_from_xy(
            [
                (0.25, 0.5),
                (5.75, 0.2),
                (6.1, 5.6),
                (0.4, 5.8),
            ]
        )

        result = PaintContourInterpolation(
            PaintContourInterpolationConfig(units="mm", fit_sample_spacing=1.0, output_spacing=1.0)
        ).build(raw)
        execution_xy = np.asarray(result.execution_path, dtype=float)[:, :2]

        self.assertGreater(len(execution_xy), 4)
        self.assertTrue(np.any(np.abs(execution_xy - np.round(execution_xy)) > 1e-6))

    def test_preserves_hard_corner_while_sampling_curve(self) -> None:
        raw = _pose_path_from_xy(
            [
                (0.0, 0.0),
                (10.0, 0.0),
                (10.0, 10.0),
                (0.0, 10.0),
            ]
        )
        interpolator = PaintContourInterpolation(
            PaintContourInterpolationConfig(
                fit_sample_spacing=1.0,
                output_spacing=1.0,
            )
        )

        result = interpolator.build(raw)
        execution_xy = np.asarray(result.execution_path, dtype=float)[:, :2]

        self.assertTrue(np.any(np.linalg.norm(execution_xy - np.asarray([10.0, 0.0]), axis=1) <= 1e-9))
        self.assertLessEqual(_max_xy_spacing(result.execution_path), 3.0 + 1e-9)

    def test_preserves_rounded_arc_shape(self) -> None:
        arc = []
        for angle_deg in np.linspace(180.0, 270.0, 18):
            radians = np.radians(angle_deg)
            arc.append((20.0 + 10.0 * np.cos(radians), 20.0 + 10.0 * np.sin(radians)))
        raw_xy = np.asarray([(0.0, 20.0), *arc, (20.0, 0.0), (40.0, 0.0), (40.0, 20.0)], dtype=float)
        raw = _pose_path_from_xy([tuple(point) for point in raw_xy])
        interpolator = PaintContourInterpolation(
            PaintContourInterpolationConfig(
                fit_sample_spacing=1.0,
                output_spacing=1.0,
                bezier_max_error=1.5,
            )
        )

        result = interpolator.build(raw)
        execution_xy = np.asarray(result.execution_path, dtype=float)[:, :2]
        raw_to_execution = _point_to_polyline_distances(raw_xy, execution_xy)
        execution_to_raw = _point_to_polyline_distances(execution_xy, raw_xy)

        self.assertLessEqual(float(np.max(raw_to_execution)), 1.6)
        self.assertLessEqual(float(np.mean(execution_to_raw)), 0.8)
        self.assertLessEqual(_max_xy_spacing(result.execution_path), 3.0 + 1e-9)

    def test_resample_contour_removes_tiny_backtrack_fold(self) -> None:
        folded_paths = [
            np.asarray(
                [
                    [11.628474, 334.760731],
                    [12.628305, 334.743211],
                    [13.628210, 334.729421],
                    [13.425821, 334.727847],
                    [14.182460, 334.708627],
                    [15.182255, 334.688399],
                ],
                dtype=float,
            ),
            np.asarray(
                [
                    [1.421070, 376.069181],
                    [2.419677, 376.016442],
                    [3.418623, 375.970628],
                    [3.017813, 376.038684],
                    [3.795902, 376.057214],
                    [4.795302, 376.022665],
                ],
                dtype=float,
            ),
        ]

        for raw_xy in folded_paths:
            with self.subTest(raw_xy=raw_xy.tolist()):
                resampled = resample_contour_xy(raw_xy, spacing=1.0, closed=False)
                vectors = np.diff(resampled, axis=0)
                lengths = np.linalg.norm(vectors, axis=1)
                unit_vectors = vectors[lengths > 1e-9] / lengths[lengths > 1e-9, None]
                turn_dots = np.sum(unit_vectors[1:] * unit_vectors[:-1], axis=1)

                self.assertGreaterEqual(len(resampled), 4)
                self.assertTrue(np.all(turn_dots > -0.95))


if __name__ == "__main__":
    unittest.main()
