from __future__ import annotations


def shutdown_workflow(workflow) -> None:
    workflow._context.set_stage(workflow._stage.SHUTDOWN, "Dropping held gripper and returning home")
    workflow._publish_diagnostics()
    result = workflow._motion.drop_gripper_if_held()
    if not result.success:
        workflow._context.mark_error(result.error)
        workflow._publish_diagnostics()
        workflow._logger.warning("%s", result.error.message)
