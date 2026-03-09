from abc import ABC, abstractmethod
from typing import List


class ISafetyChecker(ABC):

    @abstractmethod
    def is_within_safety_limits(self, position: List[float]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def is_escape_move(self, current: List[float], target: List[float]) -> bool:
        """True when already outside limits and target moves toward valid range."""
        raise NotImplementedError

    @abstractmethod
    def get_violations(self, position: List[float]) -> List[str]:
        """Returns a list of human-readable violation strings, empty if within limits."""
        ...