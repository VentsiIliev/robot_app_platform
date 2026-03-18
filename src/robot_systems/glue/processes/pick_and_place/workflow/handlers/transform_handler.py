from __future__ import annotations

from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult


def transform_pickup_point(workflow, pickup_px):
    workflow._context.set_stage(workflow._stage.TRANSFORM, "Transforming pickup point")
    workflow._context.current_pickup_point_robot_mapped = None
    workflow._context.current_pickup_tcp_delta = None
    workflow._context.current_pickup_rz = None
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
        orientation = float(workflow._context.current_orientation or 0.0)
        rz_final = float(workflow._config.rz_orientation - orientation)
        result = workflow._point_transformer.transform_to_camera_center(
            pickup_px[0],
            pickup_px[1],
            plane="pickup" if workflow._calibration_to_pickup_mapper is not None else "calibration",
            current_rz=rz_final if workflow._config.apply_pickup_plane_tcp_delta else None,
        )
        calibration_x, calibration_y = result.calibration_xy
        workflow._logger.debug(
            "Homography transformed pickup point %s -> calibration-plane robot point (%.3f, %.3f)",
            pickup_px,
            calibration_x,
            calibration_y,
        )
        if workflow._calibration_to_pickup_mapper is not None:
            robot_x, robot_y = result.plane_xy
            workflow._logger.debug(
                "Calibration-plane robot point (%.3f, %.3f) -> pickup-plane robot point (%.3f, %.3f)",
                calibration_x,
                calibration_y,
                robot_x,
                robot_y,
            )
        else:
            robot_x, robot_y = result.plane_xy
            workflow._logger.debug(
                "No calibration-to-pickup mapper configured; using calibration-plane robot point directly"
            )
        workflow._context.current_pickup_point_robot_mapped = (float(robot_x), float(robot_y))
        workflow._context.current_pickup_tcp_delta = tuple(map(float, result.pickup_plane_tcp_delta_xy))
        workflow._context.current_pickup_rz = result.current_rz
        robot_x, robot_y = result.final_xy
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
