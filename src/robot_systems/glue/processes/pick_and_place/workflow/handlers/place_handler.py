from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def execute_place_stage(workflow, drop_off_positions):
    workflow._context.set_stage(workflow._stage.PLACE, "Executing place")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("place.execute"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(error)
    place_result = workflow._motion.execute_place(drop_off_positions)
    if not place_result.success:
        workflow._context.mark_error(place_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(place_result.error)
    return None
