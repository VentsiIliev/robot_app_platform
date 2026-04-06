"""
Remaining State Handlers for Robot Calibration

This module contains the remaining state handlers that were extracted from
the main calibration pipeline. For brevity, they are combined here but
should be separated into individual files in a full refactoring.
"""

import logging
_logger = logging.getLogger(__name__)

import time
import numpy as np

from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.logging import (
    construct_align_robot_log_message,
    construct_iterative_alignment_log_message,
)
from src.engine.robot.calibration.robot_calibration.states.looking_for_aruco_markers_handler import show_live_feed
from src.engine.robot.calibration.robot_calibration.tcp_offset_capture import (
    capture_tcp_offset_for_current_marker,
    finalize_tcp_offset_calibration,
    should_capture_tcp_offset_for_current_marker,
)
from src.engine.robot.calibration.robot_calibration.ppm_utils import (
    adaptive_stability_wait,
    clear_ppm_probe,
    get_working_ppm,
    store_ppm_probe,
    try_refine_ppm,
)

wait_to_reach_position = True #TODO set to False only for testing!


def _get_target_marker_ids(context) -> list[int]:
    if getattr(context, "target_marker_ids", None):
        return list(context.target_marker_ids)
    return sorted(list(context.required_ids))


def _get_recovery_marker_id(context) -> int | None:
    recovery_marker_id = getattr(context, "recovery_marker_id", None)
    if recovery_marker_id is not None:
        return int(recovery_marker_id)
    target_ids = _get_target_marker_ids(context)
    return int(target_ids[0]) if target_ids else None


def _try_activate_fallback_target(context, failed_marker_id: int, reason: str) -> bool:
    target_ids = _get_target_marker_ids(context)
    if context.current_marker_id >= len(target_ids):
        return False

    active_ids = set(target_ids)
    neighbor_ids = getattr(context, "marker_neighbor_ids", {}).get(failed_marker_id, [])
    for candidate_id in neighbor_ids:
        if candidate_id in active_ids or candidate_id in getattr(context, "failed_target_ids", set()):
            continue
        if candidate_id not in context.markers_offsets_mm:
            continue
        old_id = target_ids[context.current_marker_id]
        target_ids[context.current_marker_id] = candidate_id
        context.target_marker_ids = target_ids
        context.failed_target_ids.add(int(old_id))
        context.skipped_target_ids.add(int(old_id))
        _logger.warning(
            "Replacing calibration target %s with nearby marker %s due to %s",
            old_id,
            candidate_id,
            reason,
        )
        return True
    return False

def handle_align_robot_state(context) -> RobotCalibrationStates:
    """
    Handle the ALIGN_ROBOT state.

    This state moves the robot to align with the current marker being calibrated.
    """
    if context.stop_event.is_set():
        return RobotCalibrationStates.CANCELLED

    required_ids_list = _get_target_marker_ids(context)
    marker_id = required_ids_list[context.current_marker_id]
    context.iteration_count = 0

    # Get marker offset and apply image-to-robot mapping
    calib_to_marker = context.markers_offsets_mm.get(marker_id, (0, 0))
    calib_to_marker_mapped = context.image_to_robot_mapping.map(
        calib_to_marker[0],
        calib_to_marker[1]
    )
    calib_to_marker = calib_to_marker_mapped

    _logger.debug(f"calib_to_marker for ID {marker_id}: {calib_to_marker}")
    current_pose = context.calibration_robot_controller.get_current_position()
    calib_pose = context.calibration_robot_controller.get_calibration_position()
    retry_attempted = False

    # Compute new target position
    x, y, z, rx, ry, rz = current_pose
    cx, cy, cz, crx, cry, crz = calib_pose

    calib_to_current = (x - cx, y - cy)
    current_to_marker = (
        calib_to_marker[0] - calib_to_current[0],
        calib_to_marker[1] - calib_to_current[1]
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
    z_new = context.Z_target
    new_position = [x_new, y_new, z_new, rx, ry, rz]

    # Move to position
    result = context.calibration_robot_controller.move_to_position(new_position, blocking=wait_to_reach_position)

    # Retry if failed
    if not result:
        retry_attempted = True
        recovery_marker_id = _get_recovery_marker_id(context)
        if recovery_marker_id in context.robot_positions_for_calibration:
            context.calibration_robot_controller.move_to_position(
                context.robot_positions_for_calibration[recovery_marker_id], blocking=wait_to_reach_position
            )
        result = context.calibration_robot_controller.move_to_position(new_position, blocking=wait_to_reach_position)

        if not result:
            # Robot movement failed after retry
            _logger.info(f"Robot movement failed for marker {marker_id} after retry attempt. ")
            _logger.info(f"Target position: {new_position}. Movement result: {result}")

            # Store specific error details for UI notification
            context.calibration_error_message = (
                f"Robot movement failed for marker {marker_id}. "
                f"Could not reach target position after retry. "
                f"Check robot safety limits and workspace boundaries."
            )
            if _try_activate_fallback_target(context, marker_id, "movement failure"):
                return RobotCalibrationStates.ALIGN_ROBOT
            return RobotCalibrationStates.ERROR

    # Log the alignment operation
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
        if context.interruptible_sleep(1.0):
            return RobotCalibrationStates.CANCELLED
        context.calibration_robot_controller.reset_derivative_state()
        clear_ppm_probe(context)        # robot teleports to new marker — invalidate probe
        context._last_error_mm_for_sampling = None  # reset so first iteration uses 1 sample
        return RobotCalibrationStates.ITERATE_ALIGNMENT
    else:
        return RobotCalibrationStates.ERROR


def handle_iterate_alignment_state(context) -> RobotCalibrationStates:
    """
    Handle the ITERATE_ALIGNMENT state.
    
    This state iteratively refines the robot position until the marker
    is aligned with the image center within the specified threshold.
    """
    required_ids_list = _get_target_marker_ids(context)
    marker_id = required_ids_list[context.current_marker_id]
    context.iteration_count += 1

    if context.iteration_count > context.max_iterations:
        # Maximum iterations exceeded - this is a calibration failure
        _logger.info(  f"Maximum iterations ({context.max_iterations}) exceeded for marker {marker_id}. "
            f"Robot failed to align with marker within threshold ({context.alignment_threshold_mm}mm). "
            f"Stopping calibration process.")
        # Store error details for UI notification
        context.calibration_error_message = (
            f"Calibration failed: Could not align with marker {marker_id} "
            f"after {context.max_iterations} iterations. "
            f"Required precision: {context.alignment_threshold_mm}mm"
        )
        if _try_activate_fallback_target(context, marker_id, "max iterations exceeded"):
            return RobotCalibrationStates.ALIGN_ROBOT
        return RobotCalibrationStates.ERROR

    # Query robot position NOW (before move) — used to refine PPM from observed pixel/mm ratio.
    _robot_pos_now = context.calibration_robot_controller.get_current_position()

    # Collect N frames and average the marker position to reduce detection noise.
    # Large errors don't need many samples — one frame is enough to know you're 10 mm off.
    # Near the threshold, averaging matters most to avoid accepting a noisy reading.
    _current_error_for_sampling = getattr(context, "_last_error_mm_for_sampling", None)
    if _current_error_for_sampling is None or _current_error_for_sampling > 5.0:
        _N_SAMPLES = 1
    elif _current_error_for_sampling > 2.0:
        _N_SAMPLES = 2
    else:
        _N_SAMPLES = 3
    image_center_px = (
        context.vision_service.get_camera_width() // 2,
        context.vision_service.get_camera_height() // 2,
    )
    newPpm = get_working_ppm(context)

    offset_samples: list = []
    iteration_image = None
    last_ids = None

    capture_start = time.time()
    for _ in range(_N_SAMPLES):
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

    marker_found = len(offset_samples) > 0

    if not marker_found:
        detected_ids = np.array(last_ids).flatten().tolist() if last_ids is not None else []
        _logger.info(
            "Marker %s not found in any of %s frames during iteration %s. Last detected IDs: %s",
            marker_id, _N_SAMPLES, context.iteration_count, detected_ids,
        )
        context.flush_camera_buffer()
        if context.interruptible_sleep(context.marker_not_found_retry_wait):
            return RobotCalibrationStates.CANCELLED
        return RobotCalibrationStates.ITERATE_ALIGNMENT  # Stay in state

    offset_x_px = float(np.mean([s[0] for s in offset_samples]))
    offset_y_px = float(np.mean([s[1] for s in offset_samples]))
    current_error_px = np.sqrt(offset_x_px ** 2 + offset_y_px ** 2)

    # ── Online PPM refinement (shared logic — see ppm_utils.py) ──────────────
    newPpm = try_refine_ppm(
        context, _robot_pos_now, current_error_px,
        label=f"marker {marker_id} iter {context.iteration_count}",
    )
    # ─────────────────────────────────────────────────────────────────────────

    current_error_mm = current_error_px / newPpm
    offset_x_mm = offset_x_px / newPpm
    offset_y_mm = offset_y_px / newPpm
    context._last_error_mm_for_sampling = current_error_mm
    processing_time = time.time() - processing_start

    alignment_success = current_error_mm <= context.alignment_threshold_mm
    movement_time = stability_time = None
    result = None

    if alignment_success:
        # Store pose and complete this marker
        start_time = time.time()
        while time.time() - start_time < 1.0:
            current_pose = context.calibration_robot_controller.get_current_position()
            time.sleep(0.05)

        _logger.info(
            "Homography sample — marker=%d  pose=[x=%.3f y=%.3f z=%.3f rx=%.4f ry=%.4f rz=%.4f]  "
            "final_error=%.3fmm  iterations=%d",
            marker_id,
            current_pose[0], current_pose[1], current_pose[2],
            current_pose[3], current_pose[4], current_pose[5],
            current_error_mm, context.iteration_count,
        )
        context.robot_positions_for_calibration[marker_id] = current_pose
        show_live_feed(context, iteration_image, current_error_mm, broadcast_image=context.broadcast_events)

        if should_capture_tcp_offset_for_current_marker(context):
            return RobotCalibrationStates.CAPTURE_TCP_OFFSET
        return RobotCalibrationStates.SAMPLE_HEIGHT
    else:
        # Compute next move
        mapped_x_mm, mapped_y_mm = context.image_to_robot_mapping.map(offset_x_mm, offset_y_mm)
        _logger.info(f"Marker {marker_id} offsets: image_mm=({offset_x_mm:.2f},{offset_y_mm:.2f}) -> "
            f"mapped_robot_mm=({mapped_x_mm:.2f},{mapped_y_mm:.2f})")

        try:
            iterative_position = context.calibration_robot_controller.get_iterative_align_position(
                current_error_mm, mapped_x_mm, mapped_y_mm, context.alignment_threshold_mm
            )
        except RuntimeError as e:
            _logger.error("Cannot compute iterative position: %s", e)
            context.calibration_error_message = str(e)
            if _try_activate_fallback_target(context, marker_id, "iterative movement failure"):
                return RobotCalibrationStates.ALIGN_ROBOT
            return RobotCalibrationStates.ERROR
        
        movement_start = time.time()
        result = context.calibration_robot_controller.move_to_position(iterative_position, blocking=wait_to_reach_position)
        movement_time = time.time() - movement_start

        # Check if iterative movement failed
        if not result:
            _logger.info(  f"Iterative robot movement failed for marker {marker_id} during iteration {context.iteration_count}. "
                f"Movement result: {result}")

            # Store specific error details for UI notification
            context.calibration_error_message = (
                f"Robot movement failed during fine alignment of marker {marker_id}. "
                f"Iteration {context.iteration_count}/{context.max_iterations}. "
                f"Check robot connectivity and safety systems."
            )
            return RobotCalibrationStates.ERROR

        # Stability wait — scale with current error as proxy for move size:
        # tiny correction near threshold settles in <0.1 s; full wait only for large moves.
        # Store probe state now so next iteration can refine PPM from this move.
        store_ppm_probe(context, _robot_pos_now, current_error_px)
        _scaled_wait = adaptive_stability_wait(context, current_error_mm)
        _logger.debug("Stability wait: %.2fs (error=%.3fmm, configured=%.1fs)", _scaled_wait, current_error_mm, context.fast_iteration_wait)
        stability_start = time.time()
        if context.interruptible_sleep(_scaled_wait):
            return RobotCalibrationStates.CANCELLED
        stability_time = time.time() - stability_start
        
        show_live_feed(context, iteration_image, current_error_mm, broadcast_image=context.broadcast_events)

    # Log iteration results
    message = construct_iterative_alignment_log_message(
        marker_id=marker_id,
        iteration=context.iteration_count,
        max_iterations=context.max_iterations,
        capture_time=capture_time,
        detection_time=detection_time,
        processing_time=processing_time,
        movement_time=movement_time,
        stability_time=stability_time,
        current_error_mm=current_error_mm,
        current_error_px=current_error_px,
        offset_mm=(offset_x_mm, offset_y_mm),
        threshold_mm=context.alignment_threshold_mm,
        alignment_success=alignment_success,
        result=result
    )
    _logger.info(message)

    return RobotCalibrationStates.ITERATE_ALIGNMENT


def handle_capture_tcp_offset_state(context) -> RobotCalibrationStates:
    if not should_capture_tcp_offset_for_current_marker(context):
        return RobotCalibrationStates.SAMPLE_HEIGHT
    if context.stop_event.is_set():
        return RobotCalibrationStates.CANCELLED
    ok = capture_tcp_offset_for_current_marker(context)
    if context.stop_event.is_set():
        return RobotCalibrationStates.CANCELLED
    if not ok:
        _logger.warning(
            "Skipping TCP offset capture for marker index %s: %s",
            context.current_marker_id,
            getattr(context, "calibration_error_message", "unknown TCP offset capture failure"),
        )
    return RobotCalibrationStates.SAMPLE_HEIGHT


def handle_done_state(context) -> RobotCalibrationStates:
    """
    Handle the DONE state.
    
    This state manages the transition between markers and final completion.
    """
    target_ids = _get_target_marker_ids(context)
    if context.current_marker_id < len(target_ids) - 1:
        # Move to the next marker
        context.current_marker_id += 1
        return RobotCalibrationStates.ALIGN_ROBOT
    else:
        # All markers processed - complete calibration
        if context.height_measuring_service and context.height_map_samples:
            _logger.info("Saving height map: %d samples", len(context.height_map_samples))
            context.height_measuring_service.save_height_map(context.height_map_samples)
        cfg = getattr(context, "camera_tcp_offset_config", None)
        if cfg is not None and getattr(cfg, "run_during_robot_calibration", False):
            ok, message = finalize_tcp_offset_calibration(context)
            if ok:
                _logger.info("Saved camera TCP offsets from main robot calibration: %s", message)
            else:
                _logger.warning("Camera TCP offset capture did not produce a saved result: %s", message)
        _logger.info("All markers processed. Calibration complete.")
        return RobotCalibrationStates.DONE  # Final completion


def handle_error_state(context) -> RobotCalibrationStates:
    """
    Handle the ERROR state.
    
    This state logs the error, sends a UI notification, and stops the calibration process.
    """
    # Get specific error message or use default
    error_message = getattr(context, 'calibration_error_message', None) or "An unknown error occurred during calibration"
    
    # Log detailed error information
    _logger.error(f"CALIBRATION FAILED: {error_message}")

    # Log additional context for debugging
    total_targets = len(_get_target_marker_ids(context))
    _logger.error( f"Calibration context: "
        f"Current marker: {context.current_marker_id}/{total_targets}, "
        f"Iteration: {context.iteration_count}/{context.max_iterations}, "
        f"Markers successfully calibrated: {len(context.robot_positions_for_calibration)}")

    
    # Send UI notification via message broker if available
    if context.broadcast_events and context.broker and hasattr(context, 'CALIBRATION_STOP_TOPIC'):
        try:
            # Create structured error notification
            error_notification = {
                    "status": "error",
                    "message": error_message,
                    "details": {
                        "current_marker": context.current_marker_id,
                    "total_markers": total_targets,
                    "successful_markers": len(context.robot_positions_for_calibration),
                    "iteration_count": context.iteration_count,
                    "max_iterations": context.max_iterations
                }
            }
            
            # Broadcast error notification to UI
            context.broker.publish(context.CALIBRATION_STOP_TOPIC, error_notification)

            _logger.info(f"Error notification sent to UI via topic: {context.CALIBRATION_STOP_TOPIC}")

            
        except Exception as e:
            import traceback
            traceback.print_exc()
            _logger.error(f"Failed to send error notification to UI: {e}")

    return RobotCalibrationStates.ERROR  # Stay in the error state
