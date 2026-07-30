from abc import ABC, abstractmethod
from typing import List, Tuple

from src.applications.workpiece_editor.i_workpiece_matcher import IWorkpieceMatcher
from src.engine.vision.i_capture_snapshot_service import VisionCaptureSnapshot


class IMatchingService(IWorkpieceMatcher, ABC):
    """Glue matching workflow, extending the editor's narrow matching port."""

    @abstractmethod
    def run_matching(self) -> Tuple[dict, int, List, List]:
        """Load workpieces, get latest contours, run matching.
        Returns (match_results_dict, no_match_count, matched, unmatched)."""
        ...

    @abstractmethod
    def get_last_capture_snapshot(self) -> VisionCaptureSnapshot | None:
        """Return the most recent capture snapshot used for matching, if any."""
        ...
