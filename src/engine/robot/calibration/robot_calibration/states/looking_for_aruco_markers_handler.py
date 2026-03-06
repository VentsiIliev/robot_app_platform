"""
Looking for ArUco Markers State Handler

Handles the state where the vision_service is looking for all required ArUco markers
in the camera feed to proceed with calibration.
"""

import cv2
import threading
import queue
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
import logging
_logger = logging.getLogger(__name__)

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
    all_aruco_detection_frame = None
    while all_aruco_detection_frame is None:
        _logger.debug("Waiting for frame for ArUco detection...")
        all_aruco_detection_frame = context.vision_service.get_latest_frame()

    # Show live feed if visualization is enabled
    if context.live_visualization:
        show_live_feed(context, all_aruco_detection_frame, 0, broadcast_image=context.broadcast_events)

    # Find required ArUco markers
    result = context.calibration_vision.find_required_aruco_markers(all_aruco_detection_frame)
    frame = result.frame
    all_found = result.found

    # Save debug image
    if context.debug:
        cv2.imwrite("new_development/NewCalibrationMethod/aruco_detection_frame.png", frame)

    if all_found:
        return RobotCalibrationStates.ALL_ARUCO_FOUND
    else:
        # Stay in current state if not all markers found
        return RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS


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


def draw_live_overlay(context, frame, current_error_mm=None):
    """Draw comprehensive live visualization overlay"""
    if not context.live_visualization:
        return frame

    from src.engine.robot.calibration.robot_calibration import visualizer

    # Get current state name
    state_name = context.get_current_state_name()

    # Draw image center (always visible)
    if hasattr(context, 'debug_draw') and context.debug_draw:
        context.debug_draw.draw_image_center(frame)

    # Draw progress bar
    progress = (context.current_marker_id / len(context.required_ids)) * 100 if context.required_ids else 0
    visualizer.draw_progress_bar(frame, progress)
    visualizer.draw_status_text(frame, state_name)

    # Current marker info
    if hasattr(context, 'current_marker_id') and context.required_ids:
        required_ids_list = sorted(list(context.required_ids))
        if context.current_marker_id < len(required_ids_list):
            current_marker = required_ids_list[context.current_marker_id]
            visualizer.draw_current_marker_info(frame, current_marker, context.current_marker_id, required_ids_list)

    # Iteration info (during iterative alignment)
    current_state = getattr(context.state_machine, 'current_state', None) if context.state_machine else None
    if current_state == RobotCalibrationStates.ITERATE_ALIGNMENT:
        visualizer.draw_iteration_info(frame, context.iteration_count, context.max_iterations)
        
        if current_error_mm is not None:
            visualizer.draw_current_error_mm(frame, current_error_mm, context.alignment_threshold_mm)

    visualizer.draw_progress_text(frame, progress)
    return frame