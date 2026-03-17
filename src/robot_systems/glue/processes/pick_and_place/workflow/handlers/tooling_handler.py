from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def ensure_gripper_ready(workflow, gripper_id: int):
    workflow._context.set_stage(workflow._stage.TOOLING, "Ensuring gripper")
    workflow._publish_diagnostics()
    gripper_result = workflow._motion.ensure_gripper(gripper_id)
    if not gripper_result.success:
        workflow._context.mark_error(gripper_result.error)
        workflow._publish_diagnostics()
        return WorkpieceProcessResult.fail(gripper_result.error)

    workflow._context.holding_gripper_id = gripper_id
    return None
