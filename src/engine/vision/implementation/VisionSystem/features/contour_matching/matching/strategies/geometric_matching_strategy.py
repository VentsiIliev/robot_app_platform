from typing import Any

import cv2
import numpy as np

from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.best_match_result import BestMatchResult
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour


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
        from src.engine.vision.implementation.VisionSystem.features.contour_matching.alignment.difference_calculator import _calculateDifferences

        best = BestMatchResult(workpiece=None, confidence=0.0, result="DIFFERENT")

        for wp in workpieces:
            wp_contour = Contour(wp.get_main_contour())
            similarity = self._getSimilarity(wp_contour.get(), contour.get())

            if similarity > self.similarity_threshold * 100 and similarity > best.confidence:
                centroid_diff, rotation_diff, contour_angle = _calculateDifferences(wp_contour, contour, self._debug_differences)
                best = BestMatchResult(
                    workpiece=wp,
                    confidence=similarity,
                    result="SAME",
                    centroid_diff=centroid_diff,
                    rotation_diff=rotation_diff,
                    contour_angle=contour_angle,
                    workpiece_id=getattr(wp, "workpieceId", None),
                )

        return best

    def _getSimilarity(self, contour1: np.ndarray, contour2: np.ndarray) -> float:
        """
        Weighted geometric similarity between two contours (0–100 %).

        Factors
        -------
        Hu moments     40 % – linear decay max (0, 1−30×d_I2)
                               d=0.000 → 1.00 (identical)
                               d=0.015 → 0.55 (triangle vs rect — was 0.985 before)
                               d≥0.033 → 0.00
        Vertex count   25 % – approxPolyDP corners exp(−|n1−n2|)
                               triangle(3) vs. rect(4) → 0.37
        Circularity 15 % – 4π·area/perim²: circle≈1.0 rect≈0.76 triangle≈0.60
        Area ratio 10 % – scale guard
        Aspect ratio   10 % – elongation guard
        """
        c1 = np.asarray(contour1, dtype=np.float32).reshape(-1, 1, 2)
        c2 = np.asarray(contour2, dtype=np.float32).reshape(-1, 1, 2)

        # --- Hu moments (linear decay) ---
        hu_dist = cv2.matchShapes(c1, c2, cv2.CONTOURS_MATCH_I2, 0.0)
        hu_sim = max(0.0, 1.0 - 30.0 * hu_dist)

        # --- Vertex count ---
        perim1 = cv2.arcLength(c1, True)
        perim2 = cv2.arcLength(c2, True)
        eps = max(0.02 * min(perim1, perim2), 1.0)
        n1 = len(cv2.approxPolyDP(c1, eps, True))
        n2 = len(cv2.approxPolyDP(c2, eps, True))
        vertex_sim = float(np.exp(-abs(n1 - n2)))

        # --- Circularity ---
        area1 = cv2.contourArea(c1)
        area2 = cv2.contourArea(c2)
        circ1 = (4.0 * np.pi * area1 / perim1 ** 2) if perim1 > 0 else 0.0
        circ2 = (4.0 * np.pi * area2 / perim2 ** 2) if perim2 > 0 else 0.0
        circ_sim = 1.0 - min(abs(circ1 - circ2), 1.0)

        # --- Area ratio ---
        area_sim = (min(area1, area2) / max(area1, area2)) if area1 > 0 and area2 > 0 else 0.0

        # --- Aspect ratio ---
        _, _, w1, h1 = cv2.boundingRect(c1)
        _, _, w2, h2 = cv2.boundingRect(c2)
        ar1 = w1 / h1 if h1 > 0 else 1.0
        ar2 = w2 / h2 if h2 > 0 else 1.0
        ar_sim = min(ar1, ar2) / max(ar1, ar2) if max(ar1, ar2) > 0 else 1.0

        # --- Weighted combination ---
        similarity_percent = float(np.clip(
            (0.40 * hu_sim + 0.25 * vertex_sim + 0.15 * circ_sim + 0.10 * area_sim + 0.10 * ar_sim) * 100,
            0.0, 100.0,
        ))

        if self._debug:
            metrics = {
                "hu_dist": hu_dist, "hu_sim": hu_sim,
                "n1": n1, "n2": n2, "vertex_sim": vertex_sim,
                "circ1": circ1, "circ2": circ2, "circ_sim": circ_sim,
                "area1": area1, "area2": area2,
                "area_diff": abs(area1 - area2), "area_ratio": area_sim,
                "aspect_ratio_sim": ar_sim,
                "similarity_percent": similarity_percent, "moment_diff": hu_dist,
            }
            from src.engine.vision.implementation.VisionSystem.features.contour_matching.debug.plot_generator import _create_debug_plot
            _create_debug_plot(contour1, contour2, metrics)
            print(
                f"[similarity] hu={hu_sim:.3f}(d={hu_dist:.4f}) "
                f"vert={vertex_sim:.3f}({n1}vs{n2}) "
                f"circ={circ_sim:.3f} area={area_sim:.3f} ar={ar_sim:.3f} "
                f"→ {similarity_percent:.1f}%"
            )

        return similarity_percent

