import logging
import unittest
from unittest.mock import MagicMock

import numpy as np

from src.applications.workpiece_editor.controller.workpiece_editor_controller import (
    WorkpieceEditorController,
)


class TestWorkpieceEditorCaptureMatching(unittest.TestCase):
    def setUp(self) -> None:
        self.controller = WorkpieceEditorController.__new__(WorkpieceEditorController)
        self.controller._model = MagicMock()
        self.controller._logger = logging.getLogger(self.__class__.__name__)
        self.controller._save_workpiece_alignment_debug_plot = MagicMock()
        self.controller._captured_pickup_point = None
        self.controller._captured_matching_contour = None

    def test_success_returns_aligned_saved_workpiece_and_payload(self) -> None:
        captured = np.asarray([[0, 0], [10, 0], [10, 5]], dtype=np.float32)
        aligned_raw = {"contour": [[20, 30], [30, 30], [30, 35]]}
        payload = {
            "raw": aligned_raw,
            "workpieceId": "trained",
            "confidence": 0.92,
        }
        self.controller._model.can_match_saved_workpieces.return_value = True
        self.controller._model.match_saved_workpieces.return_value = (
            True,
            payload,
            "Matched workpiece.",
        )

        raw, result_payload, message = self.controller._try_prepare_known_workpiece_capture(
            captured
        )

        self.assertEqual(aligned_raw, raw)
        self.assertEqual(payload, result_payload)
        self.assertEqual("", message)
        original_raw = self.controller._save_workpiece_alignment_debug_plot.call_args.args[0]
        np.testing.assert_allclose(captured, original_raw["contour"])

    def test_failure_returns_matcher_diagnostic_for_capture_message(self) -> None:
        self.controller._model.can_match_saved_workpieces.return_value = True
        self.controller._model.match_saved_workpieces.return_value = (
            False,
            None,
            "No match found. Saved workpieces checked: 1",
        )

        raw, payload, message = self.controller._try_prepare_known_workpiece_capture(
            [[0, 0], [10, 0], [10, 5]]
        )

        self.assertIsNone(raw)
        self.assertIsNone(payload)
        self.assertEqual("No match found. Saved workpieces checked: 1", message)

    def test_form_context_preserves_exact_camera_contour_for_matching(self) -> None:
        self.controller._captured_matching_contour = [
            [1.25, 2.5],
            [8.75, 2.5],
            [8.75, 9.5],
        ]

        enriched = self.controller._augment_form_data_with_editor_context({"name": "part"})

        self.assertEqual(
            self.controller._captured_matching_contour,
            enriched["matchingContour"],
        )


if __name__ == "__main__":
    unittest.main()
