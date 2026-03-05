from typing import Protocol, Any

from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.best_match_result import BestMatchResult
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour


class MatchingStrategy(Protocol):
    """Interface for contour-workpiece matching strategies."""
    def find_best_match(
        self, workpieces: list[Any], contour: Contour
    ) -> "BestMatchResult":
        ...
