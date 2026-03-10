from abc import ABC, abstractmethod
from typing import List, Tuple


class IMatchingService(ABC):

    @abstractmethod
    def run_matching(self) -> Tuple[dict, int, List, List]:
        """Load workpieces, get latest contours, run matching.
        Returns (match_results_dict, no_match_count, matched, unmatched)."""
        ...
