from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def execute_pick_stage(workflow, pickup_positions):
    workflow._context.set_stage(workflow._stage.PICK, "Executing pick")
    workflow._publish_diagnostics()
    pick_result = workflow._motion.execute_pick(pickup_positions)
    if not pick_result.success:
        workflow._context.mark_error(pick_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(pick_result.error)
    return None
