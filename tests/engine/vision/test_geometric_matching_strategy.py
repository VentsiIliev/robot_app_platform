import unittest

import cv2
import numpy as np

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.strategies.geometric_matching_strategy import (
    GeometricMatchingStrategy,
)


class _Workpiece:
    workpieceId = "saved"

    def __init__(self, contour):
        self._contour = contour

    def get_main_contour(self):
        return self._contour.copy()


class TestGeometricMatchingStrategy(unittest.TestCase):
    def setUp(self):
        self._saved = cv2.ellipse2Poly((200, 200), (80, 45), 25, 0, 360, 5).astype(np.float32)
        self._strategy = GeometricMatchingStrategy(similarity_threshold=0.7)

    def test_accepts_translated_shape_at_same_camera_scale(self):
        captured = self._saved + np.array([70, -20], dtype=np.float32)

        result = self._strategy.find_best_match([_Workpiece(self._saved)], Contour(captured))

        self.assertTrue(result.is_match)

    def test_accepts_rotated_shape_with_uneven_point_spacing(self):
        rotation = cv2.getRotationMatrix2D((200, 200), 73, 1.0)
        rotated = cv2.transform(self._saved.reshape(-1, 1, 2), rotation).reshape(-1, 2)
        captured = np.vstack([
            np.linspace(rotated[0], rotated[1], 80, endpoint=False),
            rotated[1:],
        ]).astype(np.float32)

        result = self._strategy.find_best_match([_Workpiece(self._saved)], Contour(captured))

        self.assertTrue(result.is_match)

    def test_rejects_different_silhouette_at_similar_area(self):
        square = np.array([
            [145, 145], [255, 145], [255, 255], [145, 255],
        ], dtype=np.float32)
        square = np.vstack([
            np.linspace(square[index], square[(index + 1) % 4], 25, endpoint=False)
            for index in range(4)
        ]).astype(np.float32)

        result = self._strategy.find_best_match([_Workpiece(self._saved)], Contour(square))

        self.assertFalse(result.is_match)

    def test_rejects_shape_with_much_smaller_pixel_area(self):
        captured = (self._saved - [200, 200]) * 0.35 + [500, 300]

        result = self._strategy.find_best_match([_Workpiece(self._saved)], Contour(captured))

        self.assertFalse(result.is_match)

    def test_accepts_small_camera_scale_variation(self):
        captured = (self._saved - [200, 200]) * 1.05 + [300, 250]

        result = self._strategy.find_best_match([_Workpiece(self._saved)], Contour(captured))

        self.assertTrue(result.is_match)

    def test_rejects_scale_change_that_rigid_alignment_cannot_correct(self):
        captured = (self._saved - [200, 200]) * 0.85 + [300, 250]

        result = self._strategy.find_best_match([_Workpiece(self._saved)], Contour(captured))

        self.assertFalse(result.is_match)

    def test_rejects_rounded_square_as_four_corner_square(self):
        def dense_polygon(vertices):
            points = np.asarray(vertices, dtype=np.float32)
            return np.vstack([
                np.linspace(points[index], points[(index + 1) % len(points)], 20, endpoint=False)
                for index in range(len(points))
            ]).astype(np.float32)

        rounded = dense_polygon([
            (-80, -100), (80, -100), (100, -80), (100, 80),
            (80, 100), (-80, 100), (-100, 80), (-100, -80),
        ])
        square = dense_polygon([
            (-110, -110), (110, -110), (110, 110), (-110, 110),
        ])

        result = self._strategy.find_best_match([_Workpiece(rounded)], Contour(square))

        self.assertFalse(result.is_match)

    def test_matches_mirror_and_reports_reflection(self):
        saved = np.array([
            [0, 0], [100, 0], [110, 10], [110, 50],
            [90, 60], [10, 60], [0, 50],
        ], dtype=np.float32)
        mirrored = saved.copy()
        mirrored[:, 0] *= -1

        result = self._strategy.find_best_match([_Workpiece(saved)], Contour(mirrored))

        self.assertTrue(result.is_match)
        self.assertTrue(result.reflected)

    def test_accepts_half_turn_of_asymmetric_workpiece(self):
        saved = np.array([
            [0, 0], [100, 0], [110, 10], [110, 50],
            [90, 60], [10, 60], [0, 50],
        ], dtype=np.float32)

        result = self._strategy.find_best_match([_Workpiece(saved)], Contour(-saved))

        self.assertTrue(result.is_match)
        self.assertFalse(result.reflected)


if __name__ == "__main__":
    unittest.main()
