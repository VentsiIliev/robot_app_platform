"""
Looking for Chessboard State Handler

Handles the state where the vision_service is looking for a chessboard pattern
in the camera feed to establish the reference coordinate vision_service.
"""
import logging
_logger = logging.getLogger(__name__)
import cv2
from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates
from src.engine.robot.calibration.robot_calibration.logging import construct_chessboard_state_log_message


def handle_looking_for_chessboard_state(context) -> RobotCalibrationStates:
    """
    Handle the LOOKING_FOR_CHESSBOARD state.
    
    This state captures frames and looks for a chessboard pattern to establish
    the reference coordinate vision_service and compute pixels-per-millimeter scale.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """
    # Get frame for chessboard detection
    chessboard_frame = None
    while chessboard_frame is None:
        chessboard_frame = context.vision_service.get_latest_frame()

    # Find chessboard and compute pixels per millimeter
    result = context.calibration_vision.find_chessboard_and_compute_ppm(chessboard_frame)
    found = result.found
    ppm = result.ppm
    context.bottom_left_chessboard_corner_px = result.bottom_left_px

    # Log the chessboard detection result
    message = construct_chessboard_state_log_message(
        found=found,
        ppm=ppm if found else None,
        bottom_left_corner=context.bottom_left_chessboard_corner_px,
        debug_enabled=context.debug and context.debug_draw is not None,
        detection_message=result.message
    )
    _logger.info(message)

    if found:
        # Store the pixels per millimeter for later use
        context.calibration_vision.PPM = ppm
        
        # Draw debug visualizations if enabled
        if context.debug and context.debug_draw:
            # Draw the bottom-left corner
            if context.bottom_left_chessboard_corner_px is not None:
                bottom_left_px = tuple(context.bottom_left_chessboard_corner_px.astype(int))
                cv2.circle(chessboard_frame, bottom_left_px, 8, (0, 0, 255), -1)  # Red circle
                cv2.putText(chessboard_frame, "BL", (bottom_left_px[0] + 10, bottom_left_px[1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            # Draw the chessboard center if available
            if context.chessboard_center_px is not None:
                chessboard_center_int = (int(context.chessboard_center_px[0]), int(context.chessboard_center_px[1]))
                cv2.circle(chessboard_frame, chessboard_center_int, 2, (255, 255, 0), -1)  # Yellow circle
                cv2.putText(chessboard_frame, "CB Center",
                            (chessboard_center_int[0] + 15, chessboard_center_int[1] - 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

            # Draw image center
            context.debug_draw.draw_image_center(chessboard_frame)

        # Save debug image if enabled
        if context.debug:
            cv2.imwrite("new_development/NewCalibrationMethod/chessboard_frame.png", chessboard_frame)
        
        return RobotCalibrationStates.CHESSBOARD_FOUND
    else:
        # Stay in current state if chessboard not found
        return RobotCalibrationStates.LOOKING_FOR_CHESSBOARD