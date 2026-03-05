from dataclasses import dataclass
from typing import Optional, Any

import numpy as np


@dataclass
class BestMatchResult:
    workpiece: Optional[Any]
    confidence: float
    result: str
    centroid_diff: Optional[np.ndarray] = None
    rotation_diff: Optional[float] = None
    contour_angle: Optional[float] = None
    workpiece_id: Optional[int] = None

    @property
    def is_match(self) -> bool:
        """Helper property to check if a valid match was found."""
        return self.workpiece is not None