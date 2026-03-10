from src.robot_systems.glue.processes.pick_and_place.models import PlacementTarget, WorkpieceDimensions
from src.robot_systems.glue.processes.pick_and_place.plane import Plane


class PlaneManagementService:

    def __init__(self, plane: Plane):
        self._plane = plane

    @property
    def plane(self) -> Plane:
        return self._plane

    def next_target(self, width: float, height: float) -> PlacementTarget:
        x = self._plane.xOffset + self._plane.xMin + (width / 2)
        y = self._plane.yMax - self._plane.yOffset - (height / 2)
        return PlacementTarget(x=x, y=y)

    def handle_row_overflow(self, width: float, height: float, target: PlacementTarget) -> bool:
        if target.x + (width / 2) <= self._plane.xMax:
            return False  # no overflow

        self._plane.rowCount  += 1
        self._plane.xOffset    = 0.0
        self._plane.yOffset   += self._plane.tallestContour + 50
        self._plane.tallestContour = height

        target.x = self._plane.xMin + (width / 2)
        target.y = self._plane.yMax - self._plane.yOffset - (height / 2)

        if target.y - (height / 2) < self._plane.yMin:
            self._plane.isFull = True

        return True

    def update_tallest(self, height: float) -> None:
        if height > self._plane.tallestContour:
            self._plane.tallestContour = height

    def advance_for_next(self, width: float) -> None:
        self._plane.xOffset += width + self._plane.spacing

    @property
    def is_full(self) -> bool:
        return self._plane.isFull