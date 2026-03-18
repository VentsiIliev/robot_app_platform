from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def transform_pickup_point(workflow, pickup_px):
    workflow._context.set_stage(workflow._stage.TRANSFORM, "Transforming pickup point")
    workflow._publish_diagnostics()
    if not workflow._checkpoint("transform.pickup_point"):
        error = workflow._make_error(
            workflow._error_code.CANCELLED,
            workflow._stage.CANCELLED,
            "Pick-and-place cancelled",
        )
        workflow._context.mark_error(error)
        workflow._publish_diagnostics()
        return None, None, WorkpieceProcessResult.fail(error)
    try:
        calibration_x, calibration_y = workflow._transformer.transform(pickup_px[0], pickup_px[1])
        workflow._logger.debug(
            "Homography transformed pickup point %s -> calibration-plane robot point (%.3f, %.3f)",
            pickup_px,
            calibration_x,
            calibration_y,
        )
        if workflow._calibration_to_pickup_mapper is not None:
            robot_x, robot_y = workflow._calibration_to_pickup_mapper(calibration_x, calibration_y)
            workflow._logger.debug(
                "Calibration-plane robot point (%.3f, %.3f) -> pickup-plane robot point (%.3f, %.3f)",
                calibration_x,
                calibration_y,
                robot_x,
                robot_y,
            )
        else:
            robot_x, robot_y = calibration_x, calibration_y
            workflow._logger.debug(
                "No calibration-to-pickup mapper configured; using calibration-plane robot point directly"
            )
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
