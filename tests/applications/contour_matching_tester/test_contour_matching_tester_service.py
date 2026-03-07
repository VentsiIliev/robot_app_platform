"""
Tests for contour_matching_tester service layer.

Covers:
- StubContourMatchingTesterService — interface compliance + behaviour
- ContourMatchingTesterService     — delegation + graceful fallback without optional services
"""
import unittest
from unittest.mock import MagicMock

from src.applications.contour_matching_tester.service.i_contour_matching_tester_service import IContourMatchingTesterService
from src.applications.contour_matching_tester.service.stub_contour_matching_tester_service import StubContourMatchingTesterService
from src.applications.contour_matching_tester.service.contour_matching_tester_service import ContourMatchingTesterService


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_vision_service():
    vs = MagicMock()
    vs.get_latest_contours.return_value = []
    vs.run_matching.return_value = ({}, 0, [], [])
    return vs


def _make_workpiece_service(names=None):
    ws = MagicMock()
    names = names or ["WP-1", "WP-2"]
    meta = [{"id": n, "name": n, "path": None} for n in names]
    ws.list_all.return_value = meta
    ws.load.return_value = MagicMock()
    return ws


# ══════════════════════════════════════════════════════════════════════════════
# StubContourMatchingTesterService
# ══════════════════════════════════════════════════════════════════════════════

class TestStubContourMatchingTesterService(unittest.TestCase):

    def setUp(self):
        self._stub = StubContourMatchingTesterService()

    def test_implements_interface(self):
        self.assertIsInstance(self._stub, IContourMatchingTesterService)

    def test_get_workpieces_returns_list(self):
        result = self._stub.get_workpieces()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_get_latest_contours_returns_list(self):
        result = self._stub.get_latest_contours()
        self.assertIsInstance(result, list)

    def test_run_matching_returns_tuple(self):
        result = self._stub.run_matching([], [])
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 4)

    def test_get_thumbnail_returns_none(self):
        self.assertIsNone(self._stub.get_thumbnail(0))


# ══════════════════════════════════════════════════════════════════════════════
# ContourMatchingTesterService — get_workpieces
# ══════════════════════════════════════════════════════════════════════════════

class TestContourMatchingTesterServiceGetWorkpieces(unittest.TestCase):

    def test_no_workpiece_service_returns_empty(self):
        svc = ContourMatchingTesterService(vision_service=None, workpiece_service=None)
        self.assertEqual(svc.get_workpieces(), [])

    def test_delegates_to_workpiece_service(self):
        ws  = _make_workpiece_service(["A", "B"])
        svc = ContourMatchingTesterService(workpiece_service=ws)
        result = svc.get_workpieces()
        ws.list_all.assert_called_once()
        # loaded workpieces (mocked) are returned
        self.assertEqual(len(result), 2)


# ══════════════════════════════════════════════════════════════════════════════
# ContourMatchingTesterService — run_matching
# ══════════════════════════════════════════════════════════════════════════════

class TestContourMatchingTesterServiceRunMatching(unittest.TestCase):

    def test_no_vision_service_returns_empty_tuple(self):
        svc = ContourMatchingTesterService(vision_service=None)
        result = svc.run_matching([], [])
        self.assertEqual(result, ({}, 0, [], []))

    def test_delegates_to_vision_service(self):
        vs  = _make_vision_service()
        vs.run_matching.return_value = ({"k": "v"}, 1, ["c"], ["u"])
        svc = ContourMatchingTesterService(vision_service=vs)
        result = svc.run_matching(["wp"], ["contour"])
        vs.run_matching.assert_called_once_with(["wp"], ["contour"])
        self.assertEqual(result[0], {"k": "v"})


# ══════════════════════════════════════════════════════════════════════════════
# ContourMatchingTesterService — without vision service
# ══════════════════════════════════════════════════════════════════════════════

class TestContourMatchingTesterServiceWithoutVision(unittest.TestCase):

    def test_get_latest_contours_returns_empty(self):
        svc = ContourMatchingTesterService(vision_service=None)
        self.assertEqual(svc.get_latest_contours(), [])

    def test_run_matching_returns_empty_fallback(self):
        svc = ContourMatchingTesterService(vision_service=None)
        result = svc.run_matching([], [])
        self.assertEqual(result, ({}, 0, [], []))


if __name__ == "__main__":
    unittest.main()
