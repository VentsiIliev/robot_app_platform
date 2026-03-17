from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.completion_handler import (
    finalize_placement,
)
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.pick_handler import (
    execute_pick_stage,
)
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.place_handler import (
    execute_place_stage,
)
from src.robot_systems.glue.processes.pick_and_place.workflow.handlers.planning_handler import (
    plan_placement,
)


def plan_and_execute_placement(workflow, workpiece, prepared):
    result, planning_outcome = plan_placement(workflow, prepared)
    if planning_outcome is not None:
        return planning_outcome

    pick_outcome = execute_pick_stage(workflow, prepared.pickup_positions)
    if pick_outcome is not None:
        return pick_outcome

    place_outcome = execute_place_stage(workflow, result.placement.drop_off_positions)
    if place_outcome is not None:
        return place_outcome

    return finalize_placement(workflow, workpiece, prepared, result.placement)
