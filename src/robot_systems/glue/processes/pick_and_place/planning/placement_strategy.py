from __future__ import annotations

from src.engine.vision.implementation.VisionSystem.core.models.contour import Contour
from src.robot_systems.glue.processes.pick_and_place.planning.models import PlacementResult
from src.robot_systems.glue.processes.pick_and_place.planning.placement_calculator import PlacementCalculator


class PlacementStrategy:
    def __init__(self, calculator: PlacementCalculator) -> None:
        self._calculator = calculator

    def plan(
        self,
        contour: Contour,
        orientation: float,
        workpiece_height: float,
        gripper_id: int,
    ) -> PlacementResult:
        return self._calculator.calculate(
            cnt_obj=contour,
            orientation=orientation,
            workpiece_height=workpiece_height,
            gripper_id=gripper_id,
        )
