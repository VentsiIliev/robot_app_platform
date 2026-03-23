from __future__ import annotations

from typing import Dict, Iterable, List, Mapping

from src.engine.robot.targeting.end_effector_point import EndEffectorPoint


class PointRegistry:
    """Store named end-effector points with optional alias resolution."""

    def __init__(
        self,
        points: Iterable[EndEffectorPoint],
        aliases: Mapping[str, str] | None = None,
    ) -> None:
        self._points: Dict[str, EndEffectorPoint] = {}
        for point in points:
            key = str(point.name).strip().lower()
            self._points[key] = point
        self._aliases: Dict[str, str] = {
            str(alias).strip().lower(): str(target).strip().lower()
            for alias, target in (aliases or {}).items()
        }

    def by_name(self, name: str) -> EndEffectorPoint:
        normalized = str(name).strip().lower()
        normalized = self._aliases.get(normalized, normalized)
        point = self._points.get(normalized)
        if point is None:
            raise ValueError(f"Unknown end-effector point '{name}'. Valid names: {list(self._points.keys())}")
        return point

    def names(self) -> List[str]:
        return list(self._points.keys())
