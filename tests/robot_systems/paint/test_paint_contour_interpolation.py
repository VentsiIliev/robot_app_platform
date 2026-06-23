from __future__ import annotations

import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.plan.paint_contour_interpolation import (
    PaintContourInterpolation,
    PaintContourInterpolationConfig,
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
        self.assertLessEqual(_max_xy_spacing(result.execution_path), 1.0 + 1e-9)

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
        self.assertLessEqual(_max_xy_spacing(result.execution_path), 1.0 + 1e-9)


if __name__ == "__main__":
    unittest.main()
