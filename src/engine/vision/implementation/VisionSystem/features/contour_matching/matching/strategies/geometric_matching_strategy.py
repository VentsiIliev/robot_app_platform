"""Geometric matching for contours captured by the same camera."""

import logging
from typing import Any

import cv2
import numpy as np

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.engine.vision.implementation.VisionSystem.features.contour_matching.alignment.difference_calculator import (
    _calculateDifferences,
)
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.best_match_result import (
    BestMatchResult,
)
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.normalized_mask_overlap import (
    normalized_mask_overlap,
)


_logger = logging.getLogger(__name__)
_MIN_SHAPE_OVERLAP = 0.90
_MIN_REFLECTION_ADVANTAGE = 0.02
_MIN_VERTEX_RATIO = 0.70
# Downstream alignment is rigid: it cannot scale a saved paint path.
_MIN_AREA_RATIO = 0.80


class GeometricMatchingStrategy:
    def __init__(
        self,
        similarity_threshold: float = 0.8,
        debug: bool = False,
        debug_differences: bool = False,
    ):
        self.similarity_threshold = similarity_threshold
        self._debug = debug
        self._debug_differences = debug_differences

    def find_best_match(
        self, workpieces: list[Any], contour: Contour
    ) -> BestMatchResult:
        best = BestMatchResult(workpiece=None, confidence=0.0, result="DIFFERENT")

        for workpiece in workpieces:
            saved = Contour(workpiece.get_main_contour())
            similarity, reflected = self._compare_similarity(saved.get(), contour.get())
            if similarity <= self.similarity_threshold * 100 or similarity <= best.confidence:
                continue

            aligned_source = saved
            if reflected:
                aligned_source = Contour(saved.get())
                aligned_source.reflect_horizontal(saved.getCentroid()[0])
            centroid_diff, rotation_diff, contour_angle = _calculateDifferences(
                aligned_source, contour, self._debug_differences
            )
            best = BestMatchResult(
                workpiece=workpiece,
                confidence=similarity,
                result="SAME",
                centroid_diff=centroid_diff,
                rotation_diff=rotation_diff,
                contour_angle=contour_angle,
                workpiece_id=getattr(workpiece, "workpieceId", None),
                reflected=reflected,
            )

        return best

    def _getSimilarity(self, contour1: np.ndarray, contour2: np.ndarray) -> float:
        """Return the best valid orientation's geometric agreement, as a percent."""
        similarity, _ = self._compare_similarity(contour1, contour2)
        return similarity

    def _compare_similarity(self, contour1: np.ndarray, contour2: np.ndarray) -> tuple[float, bool]:
        """Score rotations and reflections, and report the chosen orientation."""
        saved = np.asarray(contour1, dtype=np.float32).reshape(-1, 1, 2)
        captured = np.asarray(contour2, dtype=np.float32).reshape(-1, 1, 2)
        if len(saved) < 5 or len(captured) < 5:
            return 0.0, False

        saved_area = cv2.contourArea(saved)
        captured_area = cv2.contourArea(captured)
        if min(saved_area, captured_area) <= 0:
            return 0.0, False
        area_ratio = min(saved_area, captured_area) / max(saved_area, captured_area)
        if area_ratio < _MIN_AREA_RATIO:
            return 0.0, False

        saved_vertices = _structural_vertex_count(saved)
        captured_vertices = _structural_vertex_count(captured)
        vertex_ratio = min(saved_vertices, captured_vertices) / max(
            saved_vertices, captured_vertices
        )
        if vertex_ratio < _MIN_VERTEX_RATIO:
            return 0.0, False

        shape_overlap = normalized_mask_overlap(saved, captured)
        reflected = saved.copy()
        reflected[:, 0, 0] *= -1
        reflected_overlap = normalized_mask_overlap(reflected, captured)
        use_reflection = reflected_overlap > shape_overlap + _MIN_REFLECTION_ADVANTAGE
        best_overlap = reflected_overlap if use_reflection else shape_overlap
        if self._debug:
            _logger.debug(
                "Contour agreement: area=%.3f vertices=%.3f rigid=%.3f reflected=%.3f selected_reflection=%s",
                area_ratio, vertex_ratio, shape_overlap, reflected_overlap, use_reflection,
            )
        if best_overlap < _MIN_SHAPE_OVERLAP:
            return 0.0, False

        return 100.0 * min(area_ratio, best_overlap), use_reflection


def _structural_vertex_count(contour: np.ndarray) -> int:
    perimeter = cv2.arcLength(contour, True)
    return len(cv2.approxPolyDP(contour, 0.02 * perimeter, True))
