import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from src.engine.vision.vision_service import VisionService


def _make_service() -> VisionService:
    return VisionService(MagicMock())


def _wrapped(value):
    contour = MagicMock()
    contour.get.return_value = value
    return contour


class TestVisionServiceRunMatching(unittest.TestCase):

    def test_returns_four_tuple_with_expected_types(self):
        service = _make_service()

        with patch(
            "src.engine.vision.implementation.VisionSystem.features.contour_matching.find_matching_workpieces",
            return_value=({}, [], []),
        ):
            result = service.run_matching([], [])

        self.assertEqual(len(result), 4)
        self.assertIsInstance(result[0], dict)
        self.assertIsInstance(result[1], int)
        self.assertIsInstance(result[2], list)
        self.assertIsInstance(result[3], list)

    def test_empty_inputs_return_empty_result_shape(self):
        service = _make_service()

        with patch(
            "src.engine.vision.implementation.VisionSystem.features.contour_matching.find_matching_workpieces",
            return_value=({"workpieces": []}, [], []),
        ):
            result, no_match_count, matched, unmatched = service.run_matching([], [])

        self.assertEqual(result, {"workpieces": []})
        self.assertEqual(no_match_count, 0)
        self.assertEqual(matched, [])
        self.assertEqual(unmatched, [])

    def test_all_unmatched_contours_increase_no_match_count(self):
        service = _make_service()
        unmatched = [_wrapped("c1"), _wrapped("c2")]

        with patch(
            "src.engine.vision.implementation.VisionSystem.features.contour_matching.find_matching_workpieces",
            return_value=({}, unmatched, []),
        ):
            result, no_match_count, matched, unmatched_result = service.run_matching(["wp"], ["c1", "c2"])

        self.assertEqual(result, {})
        self.assertEqual(no_match_count, 2)
        self.assertEqual(matched, [])
        self.assertEqual(unmatched_result, ["c1", "c2"])

    def test_matched_and_unmatched_are_unwrapped_from_contour_objects(self):
        service = _make_service()
        matched_array = np.array([[1, 2]], dtype=np.int32)
        unmatched_array = np.array([[3, 4]], dtype=np.int32)

        with patch(
            "src.engine.vision.implementation.VisionSystem.features.contour_matching.find_matching_workpieces",
            return_value=(
                {"workpieces": [{"id": 1}]},
                [_wrapped(unmatched_array)],
                [_wrapped(matched_array)],
            ),
        ):
            result, no_match_count, matched, unmatched = service.run_matching(["wp"], ["contour"])

        self.assertEqual(result["workpieces"], [{"id": 1}])
        self.assertEqual(no_match_count, 1)
        self.assertEqual(len(matched), 1)
        self.assertEqual(len(unmatched), 1)
        self.assertTrue(np.array_equal(matched[0], matched_array))
        self.assertTrue(np.array_equal(unmatched[0], unmatched_array))

    def test_passes_workpieces_and_contours_to_matcher(self):
        service = _make_service()
        workpieces = ["wp1", "wp2"]
        contours = ["c1", "c2"]

        with patch(
            "src.engine.vision.implementation.VisionSystem.features.contour_matching.find_matching_workpieces",
            return_value=({}, [], []),
        ) as matcher:
            service.run_matching(workpieces, contours)

        matcher.assert_called_once_with(workpieces, contours)


if __name__ == "__main__":
    unittest.main()
