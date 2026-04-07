import logging
import time

import numpy as np

from src.engine.robot.calibration.robot_calibration.logging import (
    construct_iterative_alignment_log_message,
)
from src.engine.robot.calibration.robot_calibration.ppm_utils import (
    adaptive_stability_wait,
    get_working_ppm,
    store_ppm_probe,
    try_refine_ppm,
)
from src.engine.robot.calibration.robot_calibration.states.error_handling import (
    fail_calibration,
)
from src.engine.robot.calibration.robot_calibration.states.fallback_targets import (
    get_target_marker_ids,
    try_activate_fallback_target,
)
from src.engine.robot.calibration.robot_calibration.live_feed import (
    show_live_feed,
)
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import (
    RobotCalibrationStates,
)
from src.engine.robot.calibration.robot_calibration.tcp_offset_capture import (
    should_capture_tcp_offset_for_current_marker,
)


_logger = logging.getLogger(__name__)

wait_to_reach_position = True  # TODO set to False only for testing!


def _get_radial_iterative_damping(context, marker_id: int, iteration_count: int) -> float:
    if iteration_count > 2:
        return 1.0

    marker_px = context.artifacts.available_marker_points_px.get(int(marker_id))
    if marker_px is None:
        return 1.0

    image_width = float(context.vision_service.get_camera_width())
    image_height = float(context.vision_service.get_camera_height())
    center_x = image_width / 2.0
    center_y = image_height / 2.0
    max_radius = max(np.hypot(center_x, center_y), 1.0)

    marker_x, marker_y = float(marker_px[0]), float(marker_px[1])
    radial_ratio = np.hypot(marker_x - center_x, marker_y - center_y) / max_radius
    if radial_ratio <= 0.45:
        return 1.0

    severity = min((radial_ratio - 0.45) / 0.35, 1.0)
    min_scale = 0.55 if iteration_count == 1 else 0.75
    damping = 1.0 - (1.0 - min_scale) * severity
    return float(max(min_scale, min(damping, 1.0)))


def handle_iterate_alignment_state(context) -> RobotCalibrationStates:
    progress = context.progress
    artifacts = context.artifacts
    required_ids_list = get_target_marker_ids(context)
    current_marker_id = progress.current_marker_id
    marker_id = required_ids_list[current_marker_id]
    progress.iteration_count += 1

    max_iterations = progress.max_iterations
    alignment_threshold_mm = progress.alignment_threshold_mm

    if progress.iteration_count > max_iterations:
        _logger.info(
            f"Maximum iterations ({max_iterations}) exceeded for marker {marker_id}. "
            f"Robot failed to align with marker within threshold ({alignment_threshold_mm}mm). "
            f"Stopping calibration process."
        )
        message = (
            f"Calibration failed: Could not align with marker {marker_id} "
            f"after {max_iterations} iterations. "
            f"Required precision: {alignment_threshold_mm}mm"
        )
        if try_activate_fallback_target(context, marker_id, "max iterations exceeded"):
            return RobotCalibrationStates.ALIGN_ROBOT
        return fail_calibration(context, message, log_level="warning")

    robot_pos_now = context.calibration_robot_controller.get_current_position()

    current_error_for_sampling = getattr(context, "_last_error_mm_for_sampling", None)
    if current_error_for_sampling is None or current_error_for_sampling > 5.0:
        sample_count = 1
    elif current_error_for_sampling > 2.0:
        sample_count = 2
    else:
        sample_count = 3
    image_center_px = (
        context.vision_service.get_camera_width() // 2,
        context.vision_service.get_camera_height() // 2,
    )
    new_ppm = get_working_ppm(context)

    offset_samples: list = []
    iteration_image = None
    last_ids = None

    capture_start = time.time()
    for _ in range(sample_count):
        frame = context.wait_for_frame()
        if frame is None:
            return RobotCalibrationStates.CANCELLED
        iteration_image = frame
        res = context.calibration_vision.detect_specific_marker(frame, marker_id)
        if res.found and res.aruco_ids is not None:
            context.calibration_vision.update_marker_top_left_corners(
                marker_id, res.aruco_corners, res.aruco_ids
            )
            mx, my = context.calibration_vision.marker_top_left_corners[marker_id]
            offset_samples.append((float(mx) - image_center_px[0], float(my) - image_center_px[1]))
            last_ids = res.aruco_ids
    capture_time = time.time() - capture_start
    detection_time = capture_time
    processing_start = time.time()

    if not offset_samples:
        detected_ids = np.array(last_ids).flatten().tolist() if last_ids is not None else []
        _logger.info(
            "Marker %s not found in any of %s frames during iteration %s. Last detected IDs: %s",
            marker_id, sample_count, progress.iteration_count, detected_ids,
        )
        context.flush_camera_buffer()
        if context.interruptible_sleep(context.marker_not_found_retry_wait):
            return RobotCalibrationStates.CANCELLED
        return RobotCalibrationStates.ITERATE_ALIGNMENT

    offset_x_px = float(np.mean([s[0] for s in offset_samples]))
    offset_y_px = float(np.mean([s[1] for s in offset_samples]))
    current_error_px = np.sqrt(offset_x_px ** 2 + offset_y_px ** 2)

    new_ppm = try_refine_ppm(
        context, robot_pos_now, current_error_px,
        label=f"marker {marker_id} iter {progress.iteration_count}",
    )

    current_error_mm = current_error_px / new_ppm
    offset_x_mm = offset_x_px / new_ppm
    offset_y_mm = offset_y_px / new_ppm
    context._last_error_mm_for_sampling = current_error_mm
    processing_time = time.time() - processing_start

    alignment_success = current_error_mm <= alignment_threshold_mm
    movement_time = stability_time = None
    result = None

    if alignment_success:
        start_time = time.time()
        while time.time() - start_time < 0.5:
            current_pose = context.calibration_robot_controller.get_current_position()
            time.sleep(0.05)

        _logger.info(
            "Homography sample - marker=%d  pose=[x=%.3f y=%.3f z=%.3f rx=%.4f ry=%.4f rz=%.4f]  "
            "final_error=%.3fmm  iterations=%d",
            marker_id,
            current_pose[0], current_pose[1], current_pose[2],
            current_pose[3], current_pose[4], current_pose[5],
            current_error_mm, progress.iteration_count,
        )
        context.robot_positions_for_calibration[marker_id] = current_pose
        artifacts.robot_positions_for_calibration = dict(context.robot_positions_for_calibration)
        show_live_feed(context, iteration_image, current_error_mm, broadcast_image=context.broadcast_events)

        if should_capture_tcp_offset_for_current_marker(context):
            return RobotCalibrationStates.CAPTURE_TCP_OFFSET
        return RobotCalibrationStates.SAMPLE_HEIGHT

    mapped_x_mm, mapped_y_mm = context.image_to_robot_mapping.map(offset_x_mm, offset_y_mm)
    damping = _get_radial_iterative_damping(context, marker_id, progress.iteration_count)
    if damping < 1.0:
        mapped_x_mm *= damping
        mapped_y_mm *= damping
        _logger.info(
            "Applying radial iterative damping for marker %s: scale=%.2f iteration=%s",
            marker_id,
            damping,
            progress.iteration_count,
        )
    _logger.info(
        f"Marker {marker_id} offsets: image_mm=({offset_x_mm:.2f},{offset_y_mm:.2f}) -> "
        f"mapped_robot_mm=({mapped_x_mm:.2f},{mapped_y_mm:.2f})"
    )

    try:
        iterative_position = context.calibration_robot_controller.get_iterative_align_position(
            current_error_mm, mapped_x_mm, mapped_y_mm, alignment_threshold_mm
        )
    except RuntimeError as exc:
        _logger.error("Cannot compute iterative position: %s", exc)
        if try_activate_fallback_target(context, marker_id, "iterative movement failure"):
            return RobotCalibrationStates.ALIGN_ROBOT
        return fail_calibration(context, str(exc))

    movement_start = time.time()
    result = context.calibration_robot_controller.move_to_position(iterative_position, blocking=wait_to_reach_position)
    movement_time = time.time() - movement_start

    if not result:
        _logger.warning(
            "Iterative robot movement failed for marker %s during iteration %s. "
            "Attempting nearby-marker fallback before failing calibration.",
            marker_id,
            progress.iteration_count,
        )
        if try_activate_fallback_target(context, marker_id, "fine alignment movement failure"):
            return RobotCalibrationStates.ALIGN_ROBOT
        return fail_calibration(
            context,
            f"Robot movement failed during fine alignment of marker {marker_id}. "
            f"Iteration {progress.iteration_count}/{max_iterations}. "
            f"Check robot connectivity and safety systems.",
        )

    store_ppm_probe(context, robot_pos_now, current_error_px)
    scaled_wait = adaptive_stability_wait(context, current_error_mm)
    _logger.debug(
        "Stability wait: %.2fs (error=%.3fmm, configured=%.1fs)",
        scaled_wait,
        current_error_mm,
        context.fast_iteration_wait,
    )
    stability_start = time.time()
    if context.interruptible_sleep(scaled_wait):
        return RobotCalibrationStates.CANCELLED
    stability_time = time.time() - stability_start

    show_live_feed(context, iteration_image, current_error_mm, broadcast_image=context.broadcast_events)

    message = construct_iterative_alignment_log_message(
        marker_id=marker_id,
        iteration=progress.iteration_count,
        max_iterations=max_iterations,
        capture_time=capture_time,
        detection_time=detection_time,
        processing_time=processing_time,
        movement_time=movement_time,
        stability_time=stability_time,
        current_error_mm=current_error_mm,
        current_error_px=current_error_px,
        offset_mm=(offset_x_mm, offset_y_mm),
        threshold_mm=alignment_threshold_mm,
        alignment_success=alignment_success,
        result=result,
    )
    _logger.info(message)

    return RobotCalibrationStates.ITERATE_ALIGNMENT
