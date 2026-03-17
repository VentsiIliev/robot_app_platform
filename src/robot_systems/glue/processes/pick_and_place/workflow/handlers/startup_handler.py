from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import PickAndPlaceWorkflowResult


def run_startup(workflow) -> PickAndPlaceWorkflowResult | None:
    workflow._context.set_stage(workflow._stage.STARTUP, "Moving to home")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("startup.move_home"):
        return PickAndPlaceWorkflowResult.stopped("")
    move_home = workflow._motion.move_home()
    if move_home.success:
        return None

    workflow._context.mark_error(move_home.error)
    workflow._publish_diagnostics()
    return PickAndPlaceWorkflowResult.error_result(
        code=move_home.error.code,
        stage=move_home.error.stage,
        message=move_home.error.message,
        detail=move_home.error.detail,
        recoverable=move_home.error.recoverable,
    )
