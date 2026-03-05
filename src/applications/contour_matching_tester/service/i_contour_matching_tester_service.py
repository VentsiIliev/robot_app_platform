from abc import ABC, abstractmethod
from typing import Tuple


class IContourMatchingTesterService(ABC):

    @abstractmethod
    def get_workpieces(self) -> list: ...


    @abstractmethod
    def get_latest_contours(self) -> list: ...

    @abstractmethod
    def run_matching(self, workpieces: list, contours: list) -> Tuple[dict, int]:
        """Returns (match_results_dict, no_match_count)."""
        ...

