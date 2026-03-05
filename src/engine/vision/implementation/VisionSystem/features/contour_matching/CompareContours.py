# Canonical location: contour_matcher.py
# This stub exists for backward compatibility only — do not import from here in new code.
from src.engine.vision.implementation.VisionSystem.features.contour_matching.contour_matcher import (
    find_matching_workpieces,
    find_matching_workpieces as findMatchingWorkpieces,   # legacy camelCase alias
    match_workpieces,
)

__all__ = ["find_matching_workpieces", "findMatchingWorkpieces", "match_workpieces"]
