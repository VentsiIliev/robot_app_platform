from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def execute_place_stage(workflow, drop_off_positions):
    workflow._context.set_stage(workflow._stage.PLACE, "Executing place")
    workflow._publish_diagnostics()
    place_result = workflow._motion.execute_place(drop_off_positions)
    if not place_result.success:
        workflow._context.mark_error(place_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(place_result.error)
    return None
