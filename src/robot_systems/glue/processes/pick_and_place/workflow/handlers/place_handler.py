from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def _cancelled_result(workflow):
    error = workflow._make_error(
        workflow._error_code.CANCELLED,
        workflow._stage.CANCELLED,
        "Pick-and-place cancelled",
    )
    workflow._context.mark_error(error)
    workflow._publish_diagnostics()
    return WorkpieceProcessResult.fail(error)


def _execute_place_move(workflow, checkpoint: str, message: str, move_fn, drop_off_positions):
    workflow._context.set_stage(workflow._stage.PLACE, message)
    workflow._publish_diagnostics()
    if not workflow._checkpoint(checkpoint):
        return _cancelled_result(workflow)
    place_result = move_fn(drop_off_positions)
    if not place_result.success:
        workflow._context.mark_error(place_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(place_result.error)
    return None


def execute_place_approach_stage(workflow, drop_off_positions):
    return _execute_place_move(
        workflow,
        "place.approach",
        "Executing place approach",
        workflow._motion.execute_place_approach,
        drop_off_positions,
    )


def execute_place_drop_stage(workflow, drop_off_positions):
    result = _execute_place_move(
        workflow,
        "place.drop",
        "Executing place drop",
        workflow._motion.execute_place_drop,
        drop_off_positions,
    )
    if result is None:
        workflow._context.vacuum_active = False
        workflow._publish_diagnostics("Vacuum released")
    return result
