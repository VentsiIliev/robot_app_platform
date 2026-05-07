import unittest

import numpy as np

from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot
from src.robot_systems.paint.processes.paint.plan.workpiece_matching_service import (
    PaintWorkpieceMatchingService,
    pick_largest_contour,
)


def _square(size: float):
    return np.array(
        [[[0.0, 0.0]], [[size, 0.0]], [[size, size]], [[0.0, size]]],
        dtype=np.float32,
    )


def _raw_workpiece(name="Part A"):
    return {
        "workpieceId": "wp-1",
        "name": name,
        "contour": {"contour": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]]},
        "sprayPattern": {"Contour": [], "Fill": []},
        "pickupPoint": [1.0, 2.0],
    }


class TestPickLargestContour(unittest.TestCase):

    def test_returns_none_for_empty_input(self):
        self.assertIsNone(pick_largest_contour([]))

    def test_skips_invalid_contours_and_returns_largest_valid(self):
        small = _square(1.0)
        large = _square(3.0)

        result = pick_largest_contour([object(), small, "bad", large])

        self.assertTrue(np.array_equal(result, large))


class TestPaintWorkpieceMatchingService(unittest.TestCase):

    def test_can_match_saved_workpieces_requires_all_dependencies(self):
        service = PaintWorkpieceMatchingService()
        self.assertFalse(service.can_match_saved_workpieces())

    def test_match_saved_workpieces_returns_unavailable_when_dependencies_missing(self):
        service = PaintWorkpieceMatchingService()

        ok, payload, msg = service.match_saved_workpieces(_square(1.0))

        self.assertFalse(ok)
        self.assertIsNone(payload)
        self.assertEqual(msg, "Matching is not available in this editor.")

    def test_match_saved_workpieces_returns_no_saved_workpieces_when_candidates_empty(self):
        service = PaintWorkpieceMatchingService(
            list_saved_workpieces_fn=lambda: [],
            load_saved_workpiece_fn=lambda _storage_id: None,
            run_matching_fn=lambda workpieces, contours: ({}, 0, [], []),
        )

        ok, payload, msg = service.match_saved_workpieces(_square(1.0))

        self.assertFalse(ok)
        self.assertIsNone(payload)
        self.assertEqual(msg, "No saved workpieces available.")

    def test_match_saved_workpieces_returns_metadata_for_best_match(self):
        stored = [{"id": "stored-1"}]
        raw = _raw_workpiece()
        service = PaintWorkpieceMatchingService(
            list_saved_workpieces_fn=lambda: stored,
            load_saved_workpiece_fn=lambda storage_id: raw if storage_id == "stored-1" else None,
            run_matching_fn=lambda workpieces, contours: (
                {"workpieces": [workpieces[0]], "mlConfidences": ["0.75"]},
                2,
                [],
                [],
            ),
        )

        ok, payload, msg = service.match_saved_workpieces(_square(2.0))

        self.assertTrue(ok)
        self.assertEqual(msg, "Matched workpiece.")
        self.assertEqual(payload["storage_id"], "stored-1")
        self.assertEqual(payload["workpieceId"], "wp-1")
        self.assertEqual(payload["name"], "Part A")
        self.assertEqual(payload["candidate_count"], 1)
        self.assertEqual(payload["no_match_count"], 2)
        self.assertEqual(payload["confidence"], 0.75)
        self.assertEqual(payload["raw"]["pickupPoint"], [1.0, 2.0])

    def test_match_saved_workpieces_returns_no_match_message_when_result_empty(self):
        service = PaintWorkpieceMatchingService(
            list_saved_workpieces_fn=lambda: [{"id": "stored-1"}],
            load_saved_workpiece_fn=lambda _storage_id: _raw_workpiece(),
            run_matching_fn=lambda workpieces, contours: ({"workpieces": []}, 0, [], []),
        )

        ok, payload, msg = service.match_saved_workpieces(_square(1.0))

        self.assertFalse(ok)
        self.assertIsNone(payload)
        self.assertEqual(msg, "No match found. Saved workpieces checked: 1")

    def test_run_matching_caches_snapshot_and_skips_when_no_contours(self):
        snapshot = VisionCaptureSnapshot(frame="frame", contours=[], source="matching")
        capture_snapshot_service = type(
            "CaptureSnapshotServiceStub",
            (),
            {"capture_snapshot": lambda self, source="": snapshot},
        )()
        called = {"ran": False}
        service = PaintWorkpieceMatchingService(
            list_saved_workpieces_fn=lambda: [{"id": "stored-1"}],
            load_saved_workpiece_fn=lambda _storage_id: _raw_workpiece(),
            run_matching_fn=lambda workpieces, contours: called.__setitem__("ran", True),
            capture_snapshot_service=capture_snapshot_service,
        )

        result = service.run_matching()

        self.assertEqual(result, ({}, 0, [], []))
        self.assertIs(service.get_last_capture_snapshot(), snapshot)
        self.assertFalse(called["ran"])

    def test_run_matching_uses_candidates_and_snapshot_contours(self):
        snapshot = VisionCaptureSnapshot(frame="frame", contours=["c1", "c2"], source="matching")

        class _CaptureSnapshotServiceStub:
            def capture_snapshot(self, source=""):
                return snapshot

        seen = {}

        def _run_matching(workpieces, contours):
            seen["candidate_count"] = len(workpieces)
            seen["contours"] = list(contours)
            return {"workpieces": []}, 1, ["matched"], ["unmatched"]

        service = PaintWorkpieceMatchingService(
            list_saved_workpieces_fn=lambda: [{"id": "stored-1"}],
            load_saved_workpiece_fn=lambda _storage_id: _raw_workpiece(),
            run_matching_fn=_run_matching,
            capture_snapshot_service=_CaptureSnapshotServiceStub(),
        )

        result = service.run_matching()

        self.assertEqual(result, ({"workpieces": []}, 1, ["matched"], ["unmatched"]))
        self.assertEqual(seen["candidate_count"], 1)
        self.assertEqual(seen["contours"], ["c1", "c2"])


if __name__ == "__main__":
    unittest.main()
