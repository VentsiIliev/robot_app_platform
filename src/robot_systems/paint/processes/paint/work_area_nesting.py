from __future__ import annotations

from dataclasses import dataclass
import math
from threading import RLock
from typing import Sequence


@dataclass(frozen=True)
class WorkAreaNestingReservation:
    center_xy: tuple[float, float]
    width_mm: float
    height_mm: float
    has_space_for_same_footprint: bool


class WorkAreaNestingService:
    """Reserve deterministic shelf positions inside an existing work area."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.clear()

    def clear(self) -> None:
        with self._lock:
            self._signature: tuple | None = None
            self._placements: list[tuple[float, float, float, float]] = []
            self._pending: tuple[float, float, float, float] | None = None
            self._origin = (0.0, 0.0)
            self._u = (1.0, 0.0)
            self._v = (0.0, 1.0)
            self._usable = (0.0, 0.0, 0.0, 0.0)
            self._padding = 0.0

    def reserve(
        self,
        boundary_xy: Sequence[Sequence[float]],
        *,
        width_mm: float,
        height_mm: float,
        margin_mm: float,
        padding_mm: float,
    ) -> tuple[WorkAreaNestingReservation | None, str]:
        with self._lock:
            points = _finite_points(boundary_xy)
            numeric = (width_mm, height_mm, margin_mm, padding_mm)
            if (
                len(points) < 3
                or abs(_polygon_area(points)) <= 1e-6
                or not all(math.isfinite(float(value)) for value in numeric)
            ):
                return None, "Batch nesting requires a valid work area and finite dimensions"
            width, height, margin, padding = (float(value) for value in numeric)
            if width <= 0.0 or height <= 0.0 or margin < 0.0 or padding < 0.0:
                return None, "Batch nesting dimensions must be positive with non-negative spacing"
            if self._pending is not None:
                return None, "Batch nesting already has an active reservation"

            signature = tuple(round(value, 4) for point in points for value in point) + (
                round(margin, 4), round(padding, 4)
            )
            if signature != self._signature:
                self._configure(points, margin, padding)
                self._signature = signature

            left, bottom, right, top = self._usable
            candidate = self._candidate(width, height)
            if candidate is None:
                return None, "Paint work area has no space for another staged workpiece"
            x, y = candidate
            self._pending = (x, y, width, height)
            occupied = [*self._placements, self._pending]
            has_more = self._candidate(width, height, occupied=occupied) is not None
            center_u = x + width / 2.0
            center_v = y + height / 2.0
            center = (
                self._origin[0] + self._u[0] * center_u + self._v[0] * center_v,
                self._origin[1] + self._u[1] * center_u + self._v[1] * center_v,
            )
            return WorkAreaNestingReservation(center, width, height, has_more), ""

    def commit(self) -> None:
        with self._lock:
            if self._pending is not None:
                self._placements.append(self._pending)
                self._pending = None

    def cancel(self) -> None:
        with self._lock:
            self._pending = None

    def _configure(self, points: list[tuple[float, float]], margin: float, padding: float) -> None:
        origin = points[0]
        edge = next(
            (
                (point[0] - origin[0], point[1] - origin[1])
                for point in points[1:]
                if math.hypot(point[0] - origin[0], point[1] - origin[1]) > 1e-6
            ),
            (0.0, 0.0),
        )
        length = math.hypot(*edge)
        u = (edge[0] / length, edge[1] / length)
        v = (-u[1], u[0])
        projected = [
            ((point[0] - origin[0]) * u[0] + (point[1] - origin[1]) * u[1],
             (point[0] - origin[0]) * v[0] + (point[1] - origin[1]) * v[1])
            for point in points
        ]
        min_u, max_u = min(value[0] for value in projected), max(value[0] for value in projected)
        min_v, max_v = min(value[1] for value in projected), max(value[1] for value in projected)
        self._origin, self._u, self._v = origin, u, v
        self._usable = (min_u + margin, min_v + margin, max_u - margin, max_v - margin)
        self._padding = padding
        self._placements.clear()
        self._pending = None

    def _candidate(self, width: float, height: float, *, occupied=None):
        occupied = self._placements if occupied is None else occupied
        left, bottom, right, top = self._usable
        xs = {left}
        ys = {bottom}
        for x, y, item_width, item_height in occupied:
            xs.add(x + item_width + self._padding)
            ys.add(y + item_height + self._padding)
        for y in sorted(ys):
            for x in sorted(xs):
                if x + width > right or y + height > top:
                    continue
                if all(
                    x + width + self._padding <= ox
                    or ox + ow + self._padding <= x
                    or y + height + self._padding <= oy
                    or oy + oh + self._padding <= y
                    for ox, oy, ow, oh in occupied
                ):
                    return x, y
        return None


def _finite_points(points) -> list[tuple[float, float]]:
    try:
        converted = [(float(point[0]), float(point[1])) for point in points]
    except (TypeError, ValueError, IndexError):
        return []
    return converted if all(math.isfinite(value) for point in converted for value in point) else []


def _polygon_area(points: Sequence[tuple[float, float]]) -> float:
    return 0.5 * sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )
