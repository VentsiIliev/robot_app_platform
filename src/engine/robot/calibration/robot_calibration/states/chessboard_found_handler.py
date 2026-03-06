"""
Chessboard Found State Handler

Handles the state when a chessboard has been successfully detected.
This is a transition state that prepares for ArUco marker detection.
"""


import logging
_logger = logging.getLogger(__name__)

from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates

def handle_chessboard_found_state(context) -> RobotCalibrationStates:
    """
    Handle the CHESSBOARD_FOUND state.
    
    This is a simple transition state that confirms chessboard detection
    and prepares the vision_service to look for ArUco markers.
    
    Args:
        context: RobotCalibrationContext containing all calibration state
        
    Returns:
        Next state to transition to
    """

    _logger.info("CHESSBOARD FOUND at " + str(context.chessboard_center_px) + ", aligning to center...")

    # Transition directly to looking for ArUco markers
    # The chessboard detection has already stored the necessary reference points
    return RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS