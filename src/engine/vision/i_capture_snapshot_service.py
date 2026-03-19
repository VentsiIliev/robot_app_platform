from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np


@dataclass(frozen=True)
class VisionCaptureSnapshot:
    """Frame/contour snapshot paired with robot pose at capture time."""

    frame: Optional[np.ndarray]
    contours: List = field(default_factory=list)
    robot_pose: Optional[List[float]] = None
    timestamp_s: float = 0.0
    source: str = ""


class ICaptureSnapshotService(ABC):
    """Captures vision data and robot pose as one consistent runtime snapshot."""

    @abstractmethod
    def capture_snapshot(self, source: str = "") -> VisionCaptureSnapshot:
        """Return the latest frame/contours paired with the current robot pose."""

