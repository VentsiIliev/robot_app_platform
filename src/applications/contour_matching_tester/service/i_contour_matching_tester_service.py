from abc import ABC, abstractmethod
from typing import List, Optional, Tuple


class IContourMatchingTesterService(ABC):

    @abstractmethod
    def get_workpieces(self) -> list: ...

    @abstractmethod
    def get_latest_contours(self) -> list: ...

    @abstractmethod
    def run_matching(self, workpieces: list, contours: list) -> Tuple[dict, int, List, List]:
        """Returns (match_results_dict, no_match_count, matched_contours, unmatched_contours)."""
        ...

    @abstractmethod
    def get_thumbnail(self, workpiece_index: int) -> Optional[bytes]:
        """Return PNG bytes for the workpiece at the given index in the last get_workpieces() result."""
        ...
