from dataclasses import dataclass


@dataclass
class ContourMatchingSettingsData:
    similarity_threshold: float = 80.0
    refinement_threshold: float = 0.1
    debug_similarity: bool = False
    debug_calculate_differences: bool = False
    debug_align_contours: bool = False
    use_comparison_model: bool = False

