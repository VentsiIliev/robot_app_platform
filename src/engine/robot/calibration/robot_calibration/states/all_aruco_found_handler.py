"""
All ArUco Found State Handler

Handles the state when all required ArUco markers have been detected.
This state processes the markers and converts their positions from pixel to millimeter coordinates.
"""

import logging
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.logging import construct_aruco_state_log_message

_logger = logging.getLogger(__name__)

def handle_all_aruco_found_state(context) -> RobotCalibrationStates:
    """
    Handle the ALL_ARUCO_FOUND state.
    
    This state processes all detected ArUco markers and converts their pixel
    coordinates to millimeter coordinates relative to the chessboard reference.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """
    # Freeze the pre-alignment marker reference pixels for final model fitting.
    # Iterative alignment updates live marker detections near the image center,
    # which must not overwrite the original calibration correspondences.
    context.camera_points_for_homography = {
        int(marker_id): tuple(float(v) for v in top_left_corner_px)
        for marker_id, top_left_corner_px in context.calibration_vision.marker_top_left_corners.items()
    }

    # Convert marker positions from pixels to millimeters
    if context.calibration_vision.PPM is not None and context.bottom_left_chessboard_corner_px is not None:
        bottom_left_px = context.bottom_left_chessboard_corner_px

        for marker_id, top_left_corner_px in context.calibration_vision.marker_top_left_corners.items():
            # Convert to mm relative to bottom-left chessboard corner
            x_mm = (top_left_corner_px[0] - bottom_left_px[0]) / context.calibration_vision.PPM
            y_mm = (top_left_corner_px[1] - bottom_left_px[1]) / context.calibration_vision.PPM

            # Store the millimeter coordinates
            context.calibration_vision.marker_top_left_corners_mm[marker_id] = (x_mm, y_mm)

    # Build unified log message for ArUco detection results
    message = construct_aruco_state_log_message(
        detected_ids=context.calibration_vision.detected_ids,
        marker_top_left_corners_px=context.calibration_vision.marker_top_left_corners,
        marker_top_left_corners_mm=context.calibration_vision.marker_top_left_corners_mm,
        ppm=context.calibration_vision.PPM,
        bottom_left_corner_px=context.bottom_left_chessboard_corner_px,
        selected_ids=list(getattr(context, "target_marker_ids", [])),
    )

    _logger.info(message)
    _logger.info(
        "Calibration targets ready: selected_ids=%s available_ids=%s",
        list(getattr(context, "target_marker_ids", [])),
        sorted(int(marker_id) for marker_id in context.calibration_vision.marker_top_left_corners.keys()),
    )

    return RobotCalibrationStates.COMPUTE_OFFSETS
