from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def ensure_gripper_ready(workflow, gripper_id: int):
    workflow._context.set_stage(workflow._stage.TOOLING, "Ensuring gripper")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("tooling.ensure_gripper"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(error)
    gripper_result = workflow._motion.ensure_gripper(gripper_id)
    if not gripper_result.success:
        workflow._context.mark_error(gripper_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(gripper_result.error)

    if gripper_result.tool_changed:
        workflow._context.set_stage(workflow._stage.TOOLING, "Returning home after gripper pickup")
        workflow._publish_diagnostics()
        if not workflow._checkpoint("tooling.return_home"):
            error = workflow._make_error(
                workflow._error_code.CANCELLED,
                workflow._stage.CANCELLED,
                "Pick-and-place cancelled",
            )
            workflow._context.mark_error(error)
            workflow._publish_diagnostics()
            return WorkpieceProcessResult.fail(error)
        move_home_result = workflow._motion.move_home()
        if not move_home_result.success:
            error = workflow._make_error(
                workflow._error_code.MOVE_HOME_FAILED,
                workflow._stage.TOOLING,
                "Failed to return home after gripper pickup",
                detail=move_home_result.error.detail if move_home_result.error else None,
            )
            workflow._context.mark_error(error)
            workflow._publish_diagnostics()
            return WorkpieceProcessResult.fail(error)

    workflow._context.holding_gripper_id = gripper_id
    return None
