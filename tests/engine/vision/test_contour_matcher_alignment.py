import contextlib
import io
import unittest

import cv2
import numpy as np

from src.engine.vision.implementation.VisionSystem.features.contour_matching.contour_matcher import (
    find_matching_workpieces,
)
from src.engine.vision.implementation.VisionSystem.features.contour_matching.utils import (
    calculate_mask_overlap,
)


class _Workpiece:
    workpieceId = "saved"
    sprayPattern = {"Contour": [], "Fill": []}
    pickupPoint = None

    def __init__(self, points):
        self._points = points.copy()
        self.contour = {"contour": points.copy()}

    def get_main_contour(self):
        return self._points.copy()

    def get_spray_pattern_contours(self):
        return self.sprayPattern["Contour"]

    def get_spray_pattern_fills(self):
        return self.sprayPattern["Fill"]


class TestContourMatcherAlignment(unittest.TestCase):
    def setUp(self):
        self._saved = cv2.ellipse2Poly((200, 200), (80, 45), 25, 0, 360, 5).astype(np.float32)

    def _match(self, captured):
        with contextlib.redirect_stdout(io.StringIO()):
            return find_matching_workpieces([_Workpiece(self._saved)], [captured])

    def test_accepts_rigidly_aligned_workpiece(self):
        rotation = cv2.getRotationMatrix2D((200, 200), 47, 1.0)
        captured = cv2.transform(self._saved.reshape(-1, 1, 2), rotation).reshape(-1, 2)
        captured += [70, -20]

        matches, no_matches, matched_contours = self._match(captured)

        self.assertEqual(1, len(matches["workpieces"]))
        self.assertEqual(1, len(matched_contours))
        self.assertEqual([], no_matches)

    def test_rejects_same_silhouette_when_rigid_alignment_cannot_fit(self):
        captured = (self._saved - [200, 200]) * 1.10 + [300, 250]

        matches, no_matches, matched_contours = self._match(captured)

        self.assertEqual([], matches["workpieces"])
        self.assertEqual(1, len(no_matches))
        self.assertEqual([], matched_contours)

    def test_keeps_results_aligned_when_one_of_two_contours_is_rejected(self):
        good = self._saved + [70, -20]
        bad = (self._saved - [200, 200]) * 1.10 + [400, 250]

        with contextlib.redirect_stdout(io.StringIO()):
            matches, no_matches, matched_contours = find_matching_workpieces(
                [_Workpiece(self._saved)], [bad, good]
            )

        self.assertEqual(1, len(matches["workpieces"]))
        self.assertEqual(1, len(matches["mlConfidences"]))
        self.assertEqual(1, len(matched_contours))
        self.assertEqual(1, len(no_matches))
        np.testing.assert_allclose(matched_contours[0].get(), good)

    def test_half_turn_aligns_asymmetric_contour(self):
        saved = np.array([
            [0, 0], [100, 0], [110, 10], [110, 50],
            [90, 60], [10, 60], [0, 50],
        ], dtype=np.float32) + [200, 200]
        center = saved.mean(axis=0)
        captured = 2 * center - saved

        with contextlib.redirect_stdout(io.StringIO()):
            matches, no_matches, _ = find_matching_workpieces(
                [_Workpiece(saved)], [captured]
            )

        self.assertEqual([], no_matches)
        aligned = matches["workpieces"][0].contour["contour"]
        self.assertGreater(calculate_mask_overlap(aligned, captured), 0.98)

    def test_aligns_reflected_contour_and_associated_geometry(self):
        saved = np.array([
            [0, 0], [100, 0], [110, 10], [110, 50],
            [90, 60], [10, 60], [0, 50],
        ], dtype=np.float32) + [200, 200]
        captured = saved.copy()
        captured[:, 0] = 400 - captured[:, 0]

        workpiece = _Workpiece(saved)
        workpiece.sprayPattern = {
            "Contour": [{"contour": np.array([[230, 220], [250, 220], [250, 240]], dtype=np.float32)}],
            "Fill": [],
        }
        workpiece.pickupPoint = "230,230"

        with contextlib.redirect_stdout(io.StringIO()):
            matches, no_matches, _ = find_matching_workpieces(
                [workpiece], [captured]
            )

        self.assertEqual([], no_matches)
        self.assertEqual([True], matches["reflections"])
        aligned = matches["workpieces"][0]
        self.assertGreater(calculate_mask_overlap(aligned.contour["contour"], captured), 0.98)
        spray = np.asarray(aligned.sprayPattern["Contour"][0]["contour"]).reshape(-1, 2)
        np.testing.assert_allclose(spray[:, 0], [170, 150, 150], atol=2)
        pickup = [float(value) for value in aligned.pickupPoint.split(",")]
        np.testing.assert_allclose(pickup, [170, 230], atol=2)
        np.testing.assert_allclose(workpiece.get_main_contour(), saved)


if __name__ == "__main__":
    unittest.main()
