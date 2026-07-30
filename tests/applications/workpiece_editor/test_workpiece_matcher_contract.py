import unittest

from src.applications.workpiece_editor.i_workpiece_matcher import IWorkpieceMatcher
from src.robot_systems.glue.domain.matching.i_matching_service import IMatchingService
from src.robot_systems.paint.processes.paint.match.workpiece_matching_service import (
    PaintWorkpieceMatchingService,
)


class TestWorkpieceMatcherContract(unittest.TestCase):
    def test_glue_matching_contract_preserves_editor_capabilities(self):
        self.assertTrue(issubclass(IMatchingService, IWorkpieceMatcher))
        self.assertEqual(
            IMatchingService.__abstractmethods__,
            {
                "can_match_saved_workpieces",
                "match_saved_workpieces",
                "run_matching",
                "get_last_capture_snapshot",
            },
        )

    def test_paint_matching_service_implements_editor_contract(self):
        service = PaintWorkpieceMatchingService()

        self.assertIsInstance(service, IWorkpieceMatcher)
        self.assertTrue(callable(service.can_match_saved_workpieces))
        self.assertTrue(callable(service.match_saved_workpieces))


if __name__ == "__main__":
    unittest.main()
