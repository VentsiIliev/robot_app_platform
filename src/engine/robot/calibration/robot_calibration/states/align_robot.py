import logging

from src.engine.robot.calibration.robot_calibration.logging import (
    construct_align_robot_log_message,
)
from src.engine.robot.calibration.robot_calibration.ppm_utils import clear_ppm_probe
from src.engine.robot.calibration.robot_calibration.states.error_handling import (
    fail_calibration,
)
from src.engine.robot.calibration.robot_calibration.states.fallback_targets import (
    get_marker_offset_mm,
    get_recovery_marker_id,
    get_target_marker_ids,
    record_known_unreachable_marker,
    try_activate_fallback_target,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)


_logger = logging.getLogger(__name__)

wait_to_reach_position = True  # TODO set to False only for testing!


def _move_to_initial_align_target(context, target_position, marker_id):
    current_pose = context.calibration_robot_controller.get_current_position()
    current_x, current_y, _current_z, _current_rx, _current_ry, _current_rz = current_pose
    target_x, target_y, target_z, target_rx, target_ry, target_rz = target_position
    approach_z = float(
        getattr(context.calibration_robot_controller.adaptive_movement_config, "initial_align_approach_z", target_z)
    )
    staged_z = max(approach_z, float(target_z))

    staged_z_position = [current_x, current_y, staged_z, target_rx, target_ry, target_rz]
    staged_xy_position = [target_x, target_y, staged_z, target_rx, target_ry, target_rz]
    final_position = [target_x, target_y, target_z, target_rx, target_ry, target_rz]

    _logger.info(
        "Initial align staged approach for marker %s: z_stage=%s xy_stage=%s final_stage=%s",
        marker_id,
        [round(float(v), 3) for v in staged_z_position],
        [round(float(v), 3) for v in staged_xy_position],
        [round(float(v), 3) for v in final_position],
    )

    z_result = context.calibration_robot_controller.move_to_position(
        staged_z_position, blocking=wait_to_reach_position
    )
    if not z_result:
        _logger.info("Initial align Z-stage failed for marker %s", marker_id)
        return False

    xy_result = context.calibration_robot_controller.move_to_position(
        staged_xy_position, blocking=wait_to_reach_position
    )
    if not xy_result:
        _logger.info("Initial align XY-stage failed for marker %s", marker_id)
        return False

    return context.calibration_robot_controller.move_to_position(
        final_position, blocking=wait_to_reach_position
    )


def handle_align_robot_state(context) -> RobotCalibrationStates:
    if context.stop_event.is_set():
        return RobotCalibrationStates.CANCELLED

    progress = context.progress
    required_ids_list = get_target_marker_ids(context)
    current_marker_id = progress.current_marker_id
    marker_id = required_ids_list[current_marker_id]
    progress.iteration_count = 0

    calib_to_marker = get_marker_offset_mm(context, marker_id)
    calib_to_marker = context.image_to_robot_mapping.map(
        calib_to_marker[0],
        calib_to_marker[1],
    )

    _logger.debug("calib_to_marker for ID %s: %s", marker_id, calib_to_marker)
    current_pose = context.calibration_robot_controller.get_current_position()
    calib_pose = context.calibration_robot_controller.get_calibration_position()
    retry_attempted = False

    x, y, z, rx, ry, rz = current_pose
    cx, cy, cz, crx, cry, crz = calib_pose

    calib_to_current = (x - cx, y - cy)
    current_to_marker = (
        calib_to_marker[0] - calib_to_current[0],
        calib_to_marker[1] - calib_to_current[1],
    )

    initial_align_y_scale = float(
        getattr(context.calibration_robot_controller.adaptive_movement_config, "initial_align_y_scale", 1.0)
    )
    current_to_marker = (
        current_to_marker[0],
        current_to_marker[1] * initial_align_y_scale,
    )

    x_new = x + current_to_marker[0]
    y_new = y + current_to_marker[1]
    z_new = progress.z_target
    new_position = [x_new, y_new, z_new, rx, ry, rz]

    _logger.info(
        "Align target debug for marker %s: calib_pose=%s current_pose=%s raw_marker_offset_mm=%s "
        "mapped_marker_offset_mm=%s calib_to_current_mm=%s current_to_marker_mm=%s target_pose=%s",
        marker_id,
        [round(float(v), 3) for v in calib_pose],
        [round(float(v), 3) for v in current_pose],
        tuple(round(float(v), 3) for v in get_marker_offset_mm(context, marker_id)),
        tuple(round(float(v), 3) for v in calib_to_marker),
        tuple(round(float(v), 3) for v in calib_to_current),
        tuple(round(float(v), 3) for v in current_to_marker),
        [round(float(v), 3) for v in new_position],
    )

    result = _move_to_initial_align_target(context, new_position, marker_id)

    if not result:
        retry_attempted = True
        recovery_marker_id = get_recovery_marker_id(context)
        if recovery_marker_id in context.robot_positions_for_calibration:
            context.calibration_robot_controller.move_to_position(
                context.robot_positions_for_calibration[recovery_marker_id], blocking=wait_to_reach_position
            )
        result = _move_to_initial_align_target(context, new_position, marker_id)

        if not result:
            _logger.info("Robot movement failed for marker %s after retry attempt. ", marker_id)
            _logger.info("Target position: %s. Movement result: %s", new_position, result)
            record_known_unreachable_marker(context, marker_id, "align_robot_retry_failed")
            message = (
                f"Robot movement failed for marker {marker_id}. "
                f"Could not reach target position after retry. "
                f"Check robot safety limits and workspace boundaries."
            )
            if try_activate_fallback_target(context, marker_id, "movement failure"):
                return RobotCalibrationStates.ALIGN_ROBOT
            return fail_calibration(context, message)

    message = construct_align_robot_log_message(
        marker_id=marker_id,
        calib_to_marker=calib_to_marker,
        current_pose=current_pose,
        calib_pose=calib_pose,
        z_target=context.Z_target,
        result=result,
        retry_attempted=retry_attempted,
    )
    _logger.info(message)
    _logger.info(
        "Initial align compensation for marker %s: y_scale=%.3f adjusted_correction=(%.3f, %.3f)",
        marker_id,
        initial_align_y_scale,
        float(current_to_marker[0]),
        float(current_to_marker[1]),
    )

    if result:
        settle_s = float(getattr(context, "post_align_settle_s", 0.3))
        if context.interruptible_sleep(settle_s):
            return RobotCalibrationStates.CANCELLED
        context.calibration_robot_controller.reset_derivative_state()
        clear_ppm_probe(context)
        return RobotCalibrationStates.ITERATE_ALIGNMENT
    return RobotCalibrationStates.ERROR
