from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def resolve_workpiece_height(workflow, fallback_height_mm: float, robot_x: float, robot_y: float):
    workflow._context.set_stage(workflow._stage.HEIGHT, "Resolving workpiece height")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("height.resolve"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return None, WorkpieceProcessResult.fail(error)
    height_result = workflow._height_resolution.resolve(fallback_height_mm, robot_x, robot_y)
    workflow._context.active_height_source = height_result.source
    workflow._context.current_height_mm = height_result.value_mm
    if height_result.error is not None:
        workflow._context.mark_error(height_result.error)
        workflow._publish_diagnostics()
        return None, WorkpieceProcessResult.fail(height_result.error)
    return height_result.value_mm, None
