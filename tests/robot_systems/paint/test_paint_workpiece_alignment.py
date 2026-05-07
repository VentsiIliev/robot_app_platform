from __future__ import annotations

import unittest

import numpy as np

from src.robot_systems.paint.processes.paint.align import (
    DXF_ALIGNMENT_STRATEGY_REFERENCE_SMOOTH,
    align_raw_workpiece_to_contour,
)


def _raw_square(size: float = 10.0, *, offset_x: float = 0.0, offset_y: float = 0.0) -> dict:
    return {
        "workpieceId": "wp-1",
        "name": "Square",
        "contour": {
            "contour": [
                [offset_x + 0.0, offset_y + 0.0],
                [offset_x + size, offset_y + 0.0],
                [offset_x + size, offset_y + size],
                [offset_x + 0.0, offset_y + size],
            ]
        },
        "sprayPattern": {
            "Contour": [
                {
                    "contour": [
                        [[offset_x + 2.0, offset_y + 2.0]],
                        [[offset_x + 4.0, offset_y + 2.0]],
                    ]
                }
            ],
            "Fill": [
                {
                    "contour": [
                        [[offset_x + 6.0, offset_y + 6.0]],
                        [[offset_x + 8.0, offset_y + 6.0]],
                    ]
                }
            ],
        },
    }


def _cv_contour(points: list[list[float]]) -> np.ndarray:
    return np.asarray([[[float(x), float(y)]] for x, y in points], dtype=np.float32)


def _main_points(raw: dict) -> np.ndarray:
    contour = raw["contour"]["contour"] if isinstance(raw.get("contour"), dict) else raw["contour"]
    return np.asarray(contour, dtype=np.float64).reshape(-1, 2)


def _segment_points(raw: dict, key: str) -> np.ndarray:
    return np.asarray(raw["sprayPattern"][key][0]["contour"], dtype=np.float64).reshape(-1, 2)


def _polygon_area(points: np.ndarray) -> float:
    x = points[:, 0]
    y = points[:, 1]
    return 0.5 * float(abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


class TestPaintWorkpieceAlignment(unittest.TestCase):
    def test_align_raw_workpiece_to_contour_translates_main_and_spray_segments(self) -> None:
        raw = _raw_square()
        captured = _cv_contour([[20.0, 30.0], [30.0, 30.0], [30.0, 40.0], [20.0, 40.0]])

        aligned = align_raw_workpiece_to_contour(
            raw,
            captured,
            max_scale_deviation=0.0,
            reference_scale_override=1.0,
        )

        np.testing.assert_allclose(
            _main_points(aligned),
            np.array([[20.0, 30.0], [30.0, 30.0], [30.0, 40.0], [20.0, 40.0]], dtype=np.float64),
            atol=1e-3,
        )
        np.testing.assert_allclose(
            _segment_points(aligned, "Contour"),
            np.array([[22.0, 32.0], [24.0, 32.0]], dtype=np.float64),
            atol=1e-3,
        )
        np.testing.assert_allclose(
            _segment_points(aligned, "Fill"),
            np.array([[26.0, 36.0], [28.0, 36.0]], dtype=np.float64),
            atol=1e-3,
        )

    def test_align_raw_workpiece_to_contour_respects_scale_clamp(self) -> None:
        raw = _raw_square(size=10.0)
        captured = _cv_contour([[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]])

        aligned = align_raw_workpiece_to_contour(
            raw,
            captured,
            max_scale_deviation=0.0,
            reference_scale_override=1.0,
        )

        aligned_points = _main_points(aligned)
        self.assertAlmostEqual(_polygon_area(aligned_points), 100.0, places=2)

    def test_align_raw_workpiece_to_contour_returns_copy_for_degenerate_input(self) -> None:
        raw = _raw_square()
        captured = _cv_contour([[1.0, 1.0], [2.0, 2.0]])

        aligned = align_raw_workpiece_to_contour(raw, captured)

        self.assertEqual(aligned, raw)
        self.assertIsNot(aligned, raw)

    def test_reference_smooth_strategy_rewrites_main_contour_from_resampled_capture(self) -> None:
        raw = _raw_square()
        captured = _cv_contour([[15.0, 5.0], [25.0, 5.0], [25.0, 15.0], [15.0, 15.0]])

        aligned = align_raw_workpiece_to_contour(
            raw,
            captured,
            strategy=DXF_ALIGNMENT_STRATEGY_REFERENCE_SMOOTH,
            max_scale_deviation=0.0,
            reference_scale_override=1.0,
        )

        main_points = _main_points(aligned)
        self.assertGreater(len(main_points), 4)
        bbox = np.max(main_points, axis=0) - np.min(main_points, axis=0)
        np.testing.assert_allclose(bbox, np.array([10.0, 10.0], dtype=np.float64), atol=1.0)


if __name__ == "__main__":
    unittest.main()
