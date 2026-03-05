from enum import Enum


class ContourMatchingSettingKey(Enum):
    SIMILARITY_THRESHOLD        = "SIMILARITY_THRESHOLD"
    REFINEMENT_THRESHOLD        = "REFINEMENT_THRESHOLD"
    DEBUG_SIMILARITY            = "DEBUG_SIMILARITY"
    DEBUG_CALCULATE_DIFFERENCES = "DEBUG_CALCULATE_DIFFERENCES"
    DEBUG_ALIGN_CONTOURS        = "DEBUG_ALIGN_CONTOURS"
    USE_COMPARISON_MODEL        = "USE_COMPARISON_MODEL"

    def getAsLabel(self) -> str:
        return self.value + ":"

