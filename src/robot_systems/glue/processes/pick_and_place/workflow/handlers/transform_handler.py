from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def transform_pickup_point(workflow, pickup_px):
    workflow._context.set_stage(workflow._stage.TRANSFORM, "Transforming pickup point")
    workflow._publish_diagnostics()
    try:
        robot_x, robot_y = workflow._transformer.transform(pickup_px[0], pickup_px[1])
        workflow._context.current_pickup_point_robot = (float(robot_x), float(robot_y))
        return robot_x, robot_y, None
    except Exception as exc:
        workflow._logger.exception("Failed to transform pickup point")
        error = workflow._make_error(
            workflow._error_code.TRANSFORM_FAILED,
            workflow._stage.TRANSFORM,
            "Failed to transform pickup point into robot coordinates",
            detail=str(exc),
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return None, None, WorkpieceProcessResult.fail(error)
