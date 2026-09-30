import unittest
from unittest.mock import MagicMock

import numpy as np

from src.applications.contour_matching_tester.controller.contour_matching_tester_controller import (
    ContourMatchingTesterController,
)


class TestContourMatchingTesterOverlay(unittest.TestCase):
    def setUp(self):
        self.model = MagicMock()
        self.view = MagicMock()
        self.controller = ContourMatchingTesterController(self.model, self.view)
        self.controller._active = True
        self.frame = np.zeros((80, 80, 3), dtype=np.uint8)
        self.contour = np.array([[[20, 20]], [[60, 20]], [[60, 60]], [[20, 60]]])

    def test_match_overlay_is_redrawn_on_later_camera_frames(self):
        self.controller._on_camera_frame(self.frame)
        self.controller._on_match_done(({"workpieces": []}, 1, [], [self.contour]))
        self.view.update_camera_view.reset_mock()
        next_frame = np.full_like(self.frame, 30)

        self.controller._on_camera_frame(next_frame)

        displayed = self.view.update_camera_view.call_args.args[0]
        self.assertTrue(np.any(displayed != next_frame))
        np.testing.assert_array_equal(displayed[0, 0], next_frame[0, 0])

    def test_changing_workpiece_clears_match_overlay(self):
        self.controller._on_match_done(({"workpieces": []}, 1, [], [self.contour]))
        self.model.workpieces = []
        self.model.select_workpiece.return_value = False
        self.controller._on_workpiece_selected(-1)
        self.view.update_camera_view.reset_mock()

        self.controller._on_camera_frame(self.frame)

        self.assertIs(self.view.update_camera_view.call_args.args[0], self.frame)


if __name__ == "__main__":
    unittest.main()
