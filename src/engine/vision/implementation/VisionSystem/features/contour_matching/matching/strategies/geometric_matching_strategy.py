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

            similarity = self._getSimilarity(
                wp_contour.get(),
                contour.get()
            )

            if similarity > self.similarity_threshold * 100 and similarity > best.confidence:

                centroid_diff, rotation_diff, contour_angle = _calculateDifferences(
                    wp_contour,
                    contour,
                    self._debug_differences
                )

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

    # --------------------------------------------------------------

    def _normalize_contour(self, c: np.ndarray) -> np.ndarray:
        """Remove translation + scale differences safely"""

        c = np.asarray(c, dtype=np.float32).reshape(-1, 1, 2)

        # Guard against degenerate contours
        if len(c) < 3:
            return c

        M = cv2.moments(c)

        if M["m00"] != 0:
            cx = M["m10"] / M["m00"]
            cy = M["m01"] / M["m00"]

            c[:, 0, 0] -= cx
            c[:, 0, 1] -= cy

        area = cv2.contourArea(c)

        if area > 0:
            scale = np.sqrt(area)
            c /= scale

        return c

    # --------------------------------------------------------------

    def _resample_contour(self, c: np.ndarray, n: int = 128) -> np.ndarray:
        """Resample contour to fixed number of points"""
        pts = c.reshape(-1, 2)

        if len(pts) < n:
            idx = np.linspace(0, len(pts) - 1, n).astype(int)
        else:
            idx = np.linspace(0, len(pts) - 1, n).astype(int)

        pts = pts[idx]

        return pts.reshape(-1, 1, 2).astype(np.float32)

    # --------------------------------------------------------------

    def _hausdorff_similarity(self, c1: np.ndarray, c2: np.ndarray) -> float:
        """Hausdorff similarity between contours"""
        a = c1.reshape(-1, 2)
        b = c2.reshape(-1, 2)

        d1 = max(min(np.linalg.norm(p - q) for q in b) for p in a)
        d2 = max(min(np.linalg.norm(p - q) for q in a) for p in b)

        hd = max(d1, d2)

        return float(np.exp(-hd * 0.25))

    # --------------------------------------------------------------

    def _getSimilarity(self, contour1: np.ndarray, contour2: np.ndarray) -> float:
        """
        Improved geometric similarity (0–100 %)

        Metrics
        -------
        Hu moments       30 %
        Hausdorff        20 %
        Vertex count     20 %
        Circularity      10 %
        Area ratio       10 %
        Aspect ratio     10 %
        """

        c1 = np.asarray(contour1, dtype=np.float32).reshape(-1, 1, 2)
        c2 = np.asarray(contour2, dtype=np.float32).reshape(-1, 1, 2)

        if len(c1) < 5 or len(c2) < 5:
            return 0.0
        # Normalize
        c1 = self._normalize_contour(c1)
        c2 = self._normalize_contour(c2)

        # Resample
        c1 = self._resample_contour(c1)
        c2 = self._resample_contour(c2)

        # ----------------------------------------
        # Basic geometry
        # ----------------------------------------

        area1 = cv2.contourArea(c1)
        area2 = cv2.contourArea(c2)

        perim1 = cv2.arcLength(c1, True)
        perim2 = cv2.arcLength(c2, True)

        raw_area_ratio = (min(area1, area2) / max(area1, area2)) if area1 > 0 and area2 > 0 else 0.0

        # --- HARD REJECTION GATES ---
        if raw_area_ratio < 0.4:
            return 0.0

        # ----------------------------------------
        # Hu moments
        # ----------------------------------------

        hu_dist = cv2.matchShapes(c1, c2, cv2.CONTOURS_MATCH_I2, 0.0)
        hu_sim = float(np.exp(-5.0 * hu_dist))

        # ----------------------------------------
        # Hausdorff similarity
        # ----------------------------------------

        hausdorff_sim = self._hausdorff_similarity(c1, c2)

        # ----------------------------------------
        # Vertex similarity
        # ----------------------------------------
        eps1 = 0.02 * perim1
        eps2 = 0.02 * perim2

        approx1 = cv2.approxPolyDP(contour1, eps1, True)
        approx2 = cv2.approxPolyDP(contour2, eps2, True)

        n1 = len(approx1)
        n2 = len(approx2)

        if abs(n1 - n2) > 5:
            return 0.0

        vertex_sim = (min(n1, n2) / max(n1, n2)) if max(n1, n2) > 0 else 1.0

        # ----------------------------------------
        # Circularity
        # ----------------------------------------

        circ1 = (4.0 * np.pi * area1 / perim1 ** 2) if perim1 > 0 else 0.0
        circ2 = (4.0 * np.pi * area2 / perim2 ** 2) if perim2 > 0 else 0.0

        circ_sim = 1.0 - min(abs(circ1 - circ2), 1.0)

        # ----------------------------------------
        # Area similarity
        # ----------------------------------------

        area_sim = float(np.sqrt(raw_area_ratio))

        # ----------------------------------------
        # Aspect ratio
        # ----------------------------------------

        _, _, w1, h1 = cv2.boundingRect(c1)
        _, _, w2, h2 = cv2.boundingRect(c2)

        ar1 = w1 / h1 if h1 > 0 else 1.0
        ar2 = w2 / h2 if h2 > 0 else 1.0

        ar_sim = min(ar1, ar2) / max(ar1, ar2) if max(ar1, ar2) > 0 else 1.0

        # ----------------------------------------
        # Hard similarity gates (prevents compensation)
        # ----------------------------------------

        if hu_sim < 0.55:
            return 0.0

        if hausdorff_sim < 0.50:
            return 0.0

        if vertex_sim < 0.50:
            return 0.0

        if circ_sim < 0.45:
            return 0.0

        # ----------------------------------------
        # Final weighted score
        # ----------------------------------------

        similarity_percent = float(np.clip(
            (
                0.30 * hu_sim +
                0.20 * hausdorff_sim +
                0.20 * vertex_sim +
                0.10 * circ_sim +
                0.10 * area_sim +
                0.10 * ar_sim
            ) * 100,
            0.0,
            100.0,
        ))

        if self._debug:
            print(
                f"[similarity] "
                f"hu={hu_sim:.3f} "
                f"haus={hausdorff_sim:.3f} "
                f"vert={vertex_sim:.3f}({n1}vs{n2}) "
                f"circ={circ_sim:.3f} "
                f"area={area_sim:.3f} "
                f"ar={ar_sim:.3f} "
                f"→ {similarity_percent:.1f}%"
            )

        return similarity_percent