from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def plan_placement(workflow, prepared):
    workflow._context.set_stage(workflow._stage.PLANE, "Planning placement")
    workflow._publish_diagnostics()
    result = workflow._placement_strategy.plan(
        prepared.contour,
        workflow._context.current_orientation,
        prepared.workpiece_height,
        prepared.gripper_id,
    )
    if result.success:
        return result, None

    if result.plane_full:
        return None, WorkpieceProcessResult.skipped_plane_full()

    error = workflow._make_error(
        workflow._error_code.UNEXPECTED_ERROR,
        workflow._stage.PLANE,
        result.message or "Failed to calculate placement",
    )
    workflow._context.mark_error(error)
    workflow._publish_diagnostics()
    return None, WorkpieceProcessResult.fail(error)
