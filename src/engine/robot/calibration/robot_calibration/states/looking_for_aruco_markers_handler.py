"""
Looking for ArUco Markers State Handler

Handles the state where the vision_service is looking for all required ArUco markers
in the camera feed to proceed with calibration.
"""

import cv2
import threading
import queue
import numpy as np
from collections import defaultdict
from src.engine.robot.calibration.robot_calibration.overlay import draw_live_overlay
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.target_planning import build_target_selection_plan
import logging
_logger = logging.getLogger(__name__)

_N_REFERENCE_FRAMES = 10

# Global thread-safe queue for live feed frames
_live_feed_queue = queue.Queue(maxsize=2)  # Keep only latest 2 frames
_live_feed_thread = None
_live_feed_thread_stop = threading.Event()


def handle_looking_for_aruco_markers_state(context) -> RobotCalibrationStates:
    """
    Handle the LOOKING_FOR_ARUCO_MARKERS state.
    
    This state captures frames and looks for all required ArUco markers
    to proceed with the calibration process.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """
    # Flush camera buffer to get stable frame
    context.flush_camera_buffer()

    # Capture frame for ArUco detection
    all_aruco_detection_frame = context.wait_for_frame()
    if all_aruco_detection_frame is None:
        return RobotCalibrationStates.CANCELLED

    # Show live feed if visualization is enabled
    if context.live_visualization:
        show_live_feed(context, all_aruco_detection_frame, 0, broadcast_image=context.broadcast_events)

    # Find candidate markers in the current frame
    result = context.calibration_vision.find_required_aruco_markers(all_aruco_detection_frame)
    frame = result.frame

    averaged = _collect_averaged_reference_pixels(context, _N_REFERENCE_FRAMES)
    if len(averaged) >= max(4, int(getattr(context, "min_targets", 4))):
        selection_plan = build_target_selection_plan(
            averaged,
            image_width=context.vision_service.get_camera_width(),
            image_height=context.vision_service.get_camera_height(),
            min_targets=int(getattr(context, "min_targets", 4)),
            max_targets=int(getattr(context, "max_targets", 0) or len(averaged)),
            min_target_separation_px=float(getattr(context, "min_target_separation_px", 120.0)),
            preferred_ids=sorted(int(marker_id) for marker_id in getattr(context, "candidate_ids", set())),
        )
        context.available_marker_points_px = {
            int(marker_id): tuple(float(v) for v in point)
            for marker_id, point in averaged.items()
        }
        context.target_marker_ids = list(selection_plan.selected_ids)
        context.recovery_marker_id = (
            int(context.target_marker_ids[0]) if context.target_marker_ids else None
        )
        context.marker_neighbor_ids = selection_plan.neighbor_ids
        context.target_selection_report = selection_plan.report
        context.failed_target_ids.clear()
        context.skipped_target_ids.clear()
        context.calibration_vision.detected_ids = set(averaged)
        context.calibration_vision.marker_top_left_corners = dict(averaged)
        _logger.info(
            "Calibration target grid created: available_ids=%s preferred_available_ids=%s selected_ids=%s added_ids=%s rejected_ids=%s min_targets=%d max_targets=%d report=%s",
            sorted(int(marker_id) for marker_id in averaged),
            list(selection_plan.report.get("preferred_available_ids", [])),
            context.target_marker_ids,
            list(selection_plan.report.get("added_ids", [])),
            list(selection_plan.report.get("rejected_ids", [])),
            int(getattr(context, "min_targets", 4)),
            int(getattr(context, "max_targets", 0) or len(averaged)),
            selection_plan.report,
        )
        return RobotCalibrationStates.ALL_ARUCO_FOUND
    else:
        # Stay in current state if not all markers found
        _logger.info(
            "Detected %d candidate markers; waiting for at least %d before selecting calibration targets",
            len(averaged),
            max(4, int(getattr(context, "min_targets", 4))),
        )
        return RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS


def _collect_averaged_reference_pixels(context, n_frames: int) -> dict[int, np.ndarray]:
    """
    Collect n_frames detections and replace marker_top_left_corners with the
    per-marker mean position.  Only frames where a marker is actually detected
    contribute to its average, so a momentary miss does not corrupt the result.
    """
    samples = defaultdict(list)

    for _ in range(n_frames):
        if context.stop_event.is_set():
            break
        frame = context.wait_for_frame()
        if frame is None:
            break
        per_frame = context.calibration_vision.collect_reference_sample(frame, allowed_ids=None)
        for marker_id, pt in per_frame.items():
            samples[marker_id].append(pt)

    averaged = {
        marker_id: np.mean(pts, axis=0).astype(np.float32)
        for marker_id, pts in samples.items()
        if pts
    }

    if averaged:
        _logger.info(
            "Reference pixels averaged over %d frames: %s",
            n_frames,
            {k: v.tolist() for k, v in averaged.items()},
        )
    return averaged


def show_live_feed(context, frame, current_error_mm=None, window_name="Calibration Live Feed", draw_overlay=True, broadcast_image=False):
    """Show live camera feed with overlays (non-blocking)"""

    # Publish to broker immediately (this is fast)
    if broadcast_image and context.broker and context.CALIBRATION_IMAGE_TOPIC:
        context.broker.publish(context.CALIBRATION_IMAGE_TOPIC, frame)

    if not context.live_visualization:
        return False

    # Apply overlays if enabled
    if draw_overlay:
        display_frame = draw_live_overlay(context, frame.copy(), current_error_mm)
    else:
        display_frame = frame.copy()
    
    # Add frame to queue for background thread to display (non-blocking)
    try:
        # Remove old frames if queue is full
        while _live_feed_queue.full():
            try:
                _live_feed_queue.get_nowait()
            except queue.Empty:
                break
        _live_feed_queue.put_nowait((window_name, display_frame))
    except queue.Full:
        pass  # Skip if queue is full

    # Start background thread if not already running
    global _live_feed_thread
    if _live_feed_thread is None or not _live_feed_thread.is_alive():
        _live_feed_thread_stop.clear()
        _live_feed_thread = threading.Thread(
            target=_live_feed_display_worker,
            daemon=True,
            name="LiveFeedDisplayThread"
        )
        _live_feed_thread.start()

    return False  # Continue


def _live_feed_display_worker():
    """Background worker thread that displays frames from the queue"""
    while not _live_feed_thread_stop.is_set():
        try:
            # Get frame from queue with timeout
            window_name, display_frame = _live_feed_queue.get(timeout=0.1)

            # Show frame
            cv2.imshow(window_name, display_frame)

            # Check for exit key
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                _logger.info("Live feed stopped by user (q pressed)")
                _live_feed_thread_stop.set()
                break
            elif key == ord('s'):
                # Save current frame
                import time
                cv2.imwrite(f"live_capture_{time.time():.0f}.png", display_frame)
            elif key == ord('p'):
                # Pause/resume
                cv2.waitKey(0)

        except queue.Empty:
            # No frame available, just check for key presses
            cv2.waitKey(1)
            continue
        except Exception as e:
            _logger.error(f"Error in live feed display thread: {e}")
            break


def stop_live_feed_thread():
    """Stop the live feed display thread gracefully"""
    global _live_feed_thread
    _live_feed_thread_stop.set()
    if _live_feed_thread and _live_feed_thread.is_alive():
        _live_feed_thread.join(timeout=2.0)
    _live_feed_thread = None
    # Clear the queue
    while not _live_feed_queue.empty():
        try:
            _live_feed_queue.get_nowait()
        except queue.Empty:
            break

