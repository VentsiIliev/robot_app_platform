import copy
from pathlib import Path
from typing import Any, Tuple

import numpy as np

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.match_info import MatchInfo
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.best_match_result import BestMatchResult
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.strategies.matching_strategy_interface import MatchingStrategy
from src.engine.vision.implementation.VisionSystem.features.contour_matching.alignment.contour_aligner import _alignContours, prepare_data_for_alignment
from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching_config import get_settings


def _load_ml_model() -> Any:
    from src.engine.vision.implementation.VisionSystem.features.shape_matching_training.utils.io_utils import load_latest_model
    model_dir = Path(__file__).resolve().parent.parent / "shape_matching_training" / "saved_models"
    if not model_dir.exists():
        model_dir = Path.cwd() / "src" / "modules" / "shape_matching_training" / "saved_models"
    return load_latest_model(save_dir=str(model_dir))


def find_matching_workpieces(
    workpieces: list,
    new_contours: list[np.ndarray],
    debug: bool = False,
) -> tuple[dict, list, list]:
    """
    Top-level entry point: match detected contours to known workpieces and align them.

    Pipeline
    --------
    1. match_workpieces          — find best workpiece per detected contour
    2. prepare_data_for_alignment — attach Contour objects to each MatchInfo
    3. _alignContours            — rotate + translate + optional mask refinement,
                                   then call update_workpiece_data

    Args:
        workpieces:   Objects implementing get_main_contour(), get_spray_pattern_contours(),
                      get_spray_pattern_fills().
        new_contours: Raw numpy contour arrays from the camera.
        debug:        True  → override all debug flags (saves plots to debug/output/).
                      False → each flag follows ContourMatchingSettings.

    Returns:
        (final_matches dict, no_matches list, matched_contours list)
    """
    from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.strategies.geometric_matching_strategy import GeometricMatchingStrategy
    from src.engine.vision.implementation.VisionSystem.features.contour_matching.matching.strategies.ml_matching_strategy import MLMatchingStrategy

    cfg = get_settings()
    debug_similarity  = debug or cfg.get_debug_similarity()
    debug_differences = debug or cfg.get_debug_calculate_differences()
    debug_align       = debug or cfg.get_debug_align_contours()

    if cfg.get_use_comparison_model():
        strategy = MLMatchingStrategy(_load_ml_model())
    else:
        strategy = GeometricMatchingStrategy(
            similarity_threshold=cfg.get_similarity_threshold() / 100.0,
            debug=debug_similarity,
            debug_differences=debug_differences,
        )

    matched, no_matches, matched_contours = match_workpieces(workpieces, new_contours, strategy)
    final_matches = _alignContours(prepare_data_for_alignment(matched), debug=debug_align)
    return final_matches, no_matches, matched_contours


def match_workpieces(
    workpieces: list[Any],
    new_contours: list[np.ndarray],
    strategy: MatchingStrategy,
) -> Tuple[list[MatchInfo], list[Contour], list[Contour]]:
    """
    Generic matching loop — strategy-agnostic.
    Returns (matched MatchInfos, unmatched Contours, matched Contours).
    """
    matched: list[MatchInfo] = []
    no_matches: list[Contour] = []
    matched_contours: list[Contour] = []

    for contour_data in list(new_contours):
        contour = Contour(contour_data)
        best: BestMatchResult = strategy.find_best_match(workpieces, contour)

        if best.is_match:
            matched.append(MatchInfo(
                workpiece=best.workpiece,
                new_contour=contour.get(),
                centroid_diff=best.centroid_diff,
                rotation_diff=best.rotation_diff,
                contour_orientation=best.contour_angle,
                mlConfidence=best.confidence,
                mlResult=best.result,
            ))
            matched_contours.append(contour)
        else:
            no_matches.append(contour)

    return matched, no_matches, matched_contours

