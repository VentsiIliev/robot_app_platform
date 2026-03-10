from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class Position:
    x: float; y: float; z: float
    rx: float; ry: float; rz: float

    def to_list(self) -> List[float]:
        return [self.x, self.y, self.z, self.rx, self.ry, self.rz]


@dataclass
class PickupPositions:
    descent: Position
    pickup:  Position
    lift:    Position

    def __str__(self):
        return f"PickupPositions(descent={self.descent}, pickup={self.pickup}, lift={self.lift})"

@dataclass
class DropOffPositions:
    approach: Position
    drop:     Position


@dataclass
class WorkpieceDimensions:
    width:      float
    height:     float
    bbox_center: Tuple[float, float]


@dataclass
class PlacementTarget:
    x: float
    y: float


@dataclass
class WorkpiecePlacement:
    dimensions:      WorkpieceDimensions
    target_position: PlacementTarget
    pickup_positions: PickupPositions
    drop_off_positions: DropOffPositions
    pickup_height:   float


@dataclass
class PlacementResult:
    success:    bool
    placement:  Optional[WorkpiecePlacement]
    plane_full: bool
    message:    str