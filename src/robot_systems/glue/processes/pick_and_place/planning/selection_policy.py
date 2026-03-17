from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence


@dataclass(frozen=True)
class SelectedWorkpiece:
    workpiece: object
    orientation: float


class WorkpieceSelectionPolicy:
    def select(self, workpieces: Sequence[object], orientations: Sequence[float]) -> List[SelectedWorkpiece]:
        return [
            SelectedWorkpiece(workpiece=workpiece, orientation=float(orientation))
            for workpiece, orientation in zip(workpieces, orientations)
        ]
