from __future__ import annotations

import math


class DispensingMotionOps:
    def __init__(self, context) -> None:
        self._context = context

    def get_reach_start_threshold(self) -> float:
        settings = self._context.get_segment_settings()
        if settings is None:
            return 1.0
        return float(settings.reach_start_threshold)

    def is_at_current_path_start(self, threshold: float) -> bool:
        context = self._context
        pos = context.robot_service.get_current_position()
        if not pos:
            return False
        return self._dist(pos, context.path_ops.get_current_path_start_point()) < threshold

    def _dist(self, a, b) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])))
