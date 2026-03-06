"""
Compute Offsets State Handler

Handles the state where marker offsets relative to the image center are computed.
These offsets are used to calculate robot movement targets for each marker.
"""

import logging
_logger = logging.getLogger(__name__)

from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.logging import construct_compute_offsets_log_message


def handle_compute_offsets_state(context) -> RobotCalibrationStates:
    """
    Handle the COMPUTE_OFFSETS state.
    
    This state calculates the offsets of all ArUco markers relative to the image center
    in millimeter coordinates. These offsets are used later to compute robot movements.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """
    if context.calibration_vision.PPM is not None and context.bottom_left_chessboard_corner_px is not None:
        # Get image center in pixels
        image_center_px = (
            context.vision_service.get_camera_width() // 2,
            context.vision_service.get_camera_height() // 2
        )

        # Convert image center to mm relative to bottom-left of chessboard
        center_x_mm = (image_center_px[0] - context.bottom_left_chessboard_corner_px[0]) / context.calibration_vision.PPM
        center_y_mm = (image_center_px[1] - context.bottom_left_chessboard_corner_px[1]) / context.calibration_vision.PPM

        # Calculate offsets for all markers relative to image center
        for marker_id, marker_mm in context.calibration_vision.marker_top_left_corners_mm.items():
            offset_x = marker_mm[0] - center_x_mm
            offset_y = marker_mm[1] - center_y_mm
            
            # Debug output for verification
            _logger.debug(f"[CENTER_MM] {center_x_mm} {center_y_mm}")
            _logger.debug(f"[OFFSET_MM] marker {marker_id}: {offset_x} {offset_y}")

            # Store robot-space offsets for later use
            context.markers_offsets_mm[marker_id] = (offset_x, offset_y)

        # Build unified log message for offset computation
        message = construct_compute_offsets_log_message(
            ppm=context.calibration_vision.PPM,
            bottom_left_corner_px=context.bottom_left_chessboard_corner_px,
            image_center_px=image_center_px,
            marker_top_left_corners_mm=context.calibration_vision.marker_top_left_corners_mm,
            markers_offsets_mm=context.markers_offsets_mm,
        )
        _logger.info(message)

        return RobotCalibrationStates.ALIGN_ROBOT
    else:
        # Error: Missing required calibration data
        missing_data = []
        if context.calibration_vision.PPM is None:
            missing_data.append("pixels-per-mm (PPM)")
        if context.bottom_left_chessboard_corner_px is None:
            missing_data.append("chessboard corner position")
            
        error_msg = f"Missing calibration data: {', '.join(missing_data)}"
        _logger.error(f"Offset computation failed: {error_msg}")

        # Store specific error details for UI notification
        context.calibration_error_message = (
            f"Calibration failed during offset computation. "
            f"Missing required data: {', '.join(missing_data)}. "
            f"Chessboard detection may have failed."
        )
        return RobotCalibrationStates.ERROR