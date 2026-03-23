from __future__ import annotations

from src.engine.robot.plane_pose_mapper import PlanePoseMapper
from src.robot_systems.glue.processes.pick_and_place.errors import WorkpieceProcessResult
from src.robot_systems.glue.targeting import VisionPoseRequest


def transform_pickup_point(workflow, pickup_px):
    workflow._context.set_stage(workflow._stage.TRANSFORM, "Transforming pickup point")
    workflow._context.current_pickup_point_robot_mapped = None
    workflow._context.current_pickup_reference_delta = None
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
        used_mapped_resolver = False

        active_mapper = None
        capture_pose = workflow._context.current_capture_pose
        calibration_position = workflow._navigation.get_group_position("CALIBRATION")
        if capture_pose is not None and calibration_position is not None:
            active_mapper = PlanePoseMapper.from_positions(
                source_position=calibration_position,
                target_position=capture_pose,
            )
            used_mapped_resolver = True
        elif workflow._calibration_to_target_pose_mapper is not None:
            active_mapper = workflow._calibration_to_target_pose_mapper
            used_mapped_resolver = True

        result = resolve_target_point(workflow, pickup_px, rz_final, active_mapper)

        calibration_x, calibration_y = result.calibration_xy
        workflow._logger.debug(
            "Homography transformed pickup point %s -> calibration-plane robot point (%.3f, %.3f)",
            pickup_px,
            calibration_x,
            calibration_y,
        )
        if used_mapped_resolver:
            robot_x, robot_y = result.plane_xy
            workflow._logger.debug(
                "Calibration-plane robot point (%.3f, %.3f) -> mapped robot point (%.3f, %.3f)",
                calibration_x,
                calibration_y,
                robot_x,
                robot_y,
            )
        else:
            robot_x, robot_y = result.plane_xy
            workflow._logger.debug(
                "No calibration-to-target-pose mapper configured; using calibration-plane robot point directly"
            )
        workflow._context.current_pickup_point_robot_mapped = (float(robot_x), float(robot_y))
        workflow._context.current_pickup_reference_delta = tuple(map(float, result.pickup_plane_reference_delta_xy))
        workflow._context.current_pickup_rz = result.rz
        robot_x, robot_y = result.final_xy
        if workflow._config.pickup_target in {"gripper", "tool"}:
            workflow._logger.debug(
                "Applied %s target delta at rz_degrees=%.3f -> (%.3f, %.3f); final pickup target (%.3f, %.3f)",
                workflow._config.pickup_target,
                rz_final,
                result.target_delta_xy[0],
                result.target_delta_xy[1],
                robot_x,
                robot_y,
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


def resolve_target_point(workflow, pickup_px, rz_final, active_mapper):
    target = workflow._config.pickup_target
    target_request = VisionPoseRequest(
        x_pixels=pickup_px[0],
        y_pixels=pickup_px[1],
        z_mm=0.0,
        rz_degrees=rz_final,
        rx_degrees=workflow._config.orientation_rx,
        ry_degrees=workflow._config.orientation_ry,
    )
    return workflow._resolver.resolve_named(target_request, target, mapper=active_mapper)
