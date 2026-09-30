import unittest
from unittest.mock import MagicMock

from src.applications.contour_matching_tester.model.contour_matching_tester_model import (
    ContourMatchingTesterModel,
)


class TestContourMatchingTesterModel(unittest.TestCase):
    def test_matches_selected_workpiece_against_every_detected_contour(self):
        service = MagicMock()
        first, selected, third = object(), object(), object()
        contours = [object(), object(), object()]
        service.get_workpieces.return_value = [first, selected, third]
        service.get_latest_contours.return_value = contours
        service.run_matching.return_value = (
            {"workpieces": [selected]}, 2, [contours[1]], [contours[0], contours[2]]
        )
        model = ContourMatchingTesterModel(service)

        model.load_workpieces()
        self.assertTrue(model.select_workpiece(1))
        result = model.run_matching(1)

        service.run_matching.assert_called_once_with([selected], contours)
        self.assertEqual(2, result[1])

    def test_reloading_workpieces_clears_selection(self):
        service = MagicMock()
        service.get_workpieces.return_value = [object()]
        model = ContourMatchingTesterModel(service)

        model.load_workpieces()
        model.select_workpiece(0)
        model.load_workpieces()

        self.assertIsNone(model.selected_index)
        with self.assertRaisesRegex(ValueError, "Select a saved workpiece"):
            model.run_matching(-1)

    def test_clearing_selection_prevents_matching(self):
        service = MagicMock()
        service.get_workpieces.return_value = [object()]
        model = ContourMatchingTesterModel(service)

        model.load_workpieces()
        model.select_workpiece(0)
        self.assertFalse(model.select_workpiece(-1))

        self.assertIsNone(model.selected_index)
        with self.assertRaisesRegex(ValueError, "Select a saved workpiece"):
            model.run_matching(-1)
        service.run_matching.assert_not_called()


if __name__ == "__main__":
    unittest.main()
