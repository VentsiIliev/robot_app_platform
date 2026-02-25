from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class RobotStateSnapshot:
    state:        str
    position:     List[float]
    velocity:     float
    acceleration: float
    extra:        Dict[str, Any] = field(default_factory=dict)

    def with_extra(self, **kwargs) -> RobotStateSnapshot:
        """Return a new snapshot with additional fields merged into extra."""
        return RobotStateSnapshot(
            state=self.state,
            position=self.position,
            velocity=self.velocity,
            acceleration=self.acceleration,
            extra={**self.extra, **kwargs},
        )
