from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass(frozen=True)
class WorkpiecePlacedEvent:
    workpiece_name: str
    gripper_id:     int
    plane_x:        float
    plane_y:        float
    width:          float
    height:         float
    timestamp:      datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass(frozen=True)
class MatchedWorkpieceInfo:
    workpiece_name: str
    workpiece_id:   str
    gripper_id:     int
    orientation:    float


@dataclass(frozen=True)
class PickAndPlaceDiagnosticsEvent:
    snapshot: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class PickAndPlaceTopics:
    WORKPIECE_PLACED = "pick_and_place/workpiece_placed"
    PLANE_RESET      = "pick_and_place/plane_reset"
    MATCH_RESULT = "pick_and_place/match_result"
    DIAGNOSTICS = "pick_and_place/diagnostics"
