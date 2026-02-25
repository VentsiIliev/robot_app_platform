from abc import ABC, abstractmethod
from typing import List


class ISafetyChecker(ABC):

    @abstractmethod
    def is_within_safety_limits(self, position: List[float]) -> bool:
        raise NotImplementedError
