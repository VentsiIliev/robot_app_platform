from typing import Any

from src.engine.vision.implementation.VisionSystem.features.contour_matching.alignment.difference_calculator import _calculateDifferences
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.best_match_result import BestMatchResult
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching_config import get_settings
from src.engine.vision.implementation.VisionSystem.features.shape_matching_training.utils.io_utils import predict_similarity
from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour


class MLMatchingStrategy:
    def __init__(self, model: Any):
        self.model = model

    def find_best_match(
        self, workpieces: list[Any], contour: Contour
    ) -> BestMatchResult:


        best = BestMatchResult(workpiece=None, confidence=0.0, result="DIFFERENT")

        for wp in workpieces:
            wp_contour = Contour(wp.get_main_contour())
            result, confidence, _ = predict_similarity(self.model, wp_contour.get(), contour.get())
            wp_id = getattr(wp, "workpieceId", None)

            if result == "SAME":
                if best.workpiece is None or confidence > best.confidence:
                    centroid_diff, rotation_diff, contour_angle = _calculateDifferences(
                        wp_contour, contour, get_settings().get_debug_calculate_differences()
                    )
                    best = BestMatchResult(
                        workpiece=wp,
                        confidence=confidence,
                        result=result,
                        centroid_diff=centroid_diff,
                        rotation_diff=rotation_diff,
                        contour_angle=contour_angle,
                        workpiece_id=wp_id,
                    )
            elif best.workpiece is None and confidence > best.confidence:
                best = BestMatchResult(
                    workpiece=None,
                    confidence=confidence,
                    result=result,
                    workpiece_id=wp_id,
                )

        return best

