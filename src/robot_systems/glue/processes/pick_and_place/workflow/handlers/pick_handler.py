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


def _execute_pick_move(workflow, checkpoint: str, message: str, move_fn, pickup_positions):
    workflow._context.set_stage(workflow._stage.PICK, message)
    workflow._publish_diagnostics()
    if not workflow._checkpoint(checkpoint):
        return _cancelled_result(workflow)
    pick_result = move_fn(pickup_positions)
    if not pick_result.success:
        workflow._context.mark_error(pick_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(pick_result.error)
    return None


def execute_pick_descent_stage(workflow, pickup_positions):
    return _execute_pick_move(
        workflow,
        "pick.descent",
        "Executing pick descent",
        workflow._motion.execute_pick_descent,
        pickup_positions,
    )


def execute_pick_contact_stage(workflow, pickup_positions):
    return _execute_pick_move(
        workflow,
        "pick.pickup",
        "Executing pick contact",
        workflow._motion.execute_pickup_contact,
        pickup_positions,
    )


def execute_pick_lift_stage(workflow, pickup_positions):
    return _execute_pick_move(
        workflow,
        "pick.lift",
        "Executing pick lift",
        workflow._motion.execute_pick_lift,
        pickup_positions,
    )
