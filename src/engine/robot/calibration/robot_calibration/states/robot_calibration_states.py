from enum import Enum, auto
from typing import Dict, Set


class RobotCalibrationStates(Enum):
    INITIALIZING = auto()
    AXIS_MAPPING = auto()
    LOOKING_FOR_CHESSBOARD = auto()
    CHESSBOARD_FOUND = auto()
    ALIGN_TO_CHESSBOARD_CENTER = auto()
    LOOKING_FOR_ARUCO_MARKERS = auto()
    ALL_ARUCO_FOUND = auto()
    COMPUTE_OFFSETS = auto()
    ALIGN_ROBOT = auto()
    ITERATE_ALIGNMENT = auto()
    SAMPLE_HEIGHT = auto()
    DONE = auto()
    ERROR = auto()


class RobotCalibrationTransitionRules:
    """
    Transition rules for robot calibration process.
    
    These rules define the valid state transitions for robot calibration operations.
    """
    
    @staticmethod
    def get_calibration_transition_rules() -> Dict[RobotCalibrationStates, Set[RobotCalibrationStates]]:
        """
        Get the complete transition rules for robot calibration operations.
        
        Returns:
            Dict mapping calibration states to their valid transition targets
        """
        return {
            RobotCalibrationStates.INITIALIZING: {
                RobotCalibrationStates.AXIS_MAPPING,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.AXIS_MAPPING: {
                RobotCalibrationStates.LOOKING_FOR_CHESSBOARD,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.LOOKING_FOR_CHESSBOARD: {
                RobotCalibrationStates.CHESSBOARD_FOUND,
                RobotCalibrationStates.LOOKING_FOR_CHESSBOARD,  # Allow staying in state
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.CHESSBOARD_FOUND: {
                RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS,
                RobotCalibrationStates.ALIGN_TO_CHESSBOARD_CENTER,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.ALIGN_TO_CHESSBOARD_CENTER: {
                RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS: {
                RobotCalibrationStates.ALL_ARUCO_FOUND,
                RobotCalibrationStates.LOOKING_FOR_ARUCO_MARKERS,  # Allow staying in state
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.ALL_ARUCO_FOUND: {
                RobotCalibrationStates.COMPUTE_OFFSETS,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.COMPUTE_OFFSETS: {
                RobotCalibrationStates.ALIGN_ROBOT,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.ALIGN_ROBOT: {
                RobotCalibrationStates.ITERATE_ALIGNMENT,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.ITERATE_ALIGNMENT: {
                RobotCalibrationStates.ITERATE_ALIGNMENT,  # Allow staying for multiple iterations
                RobotCalibrationStates.DONE,  # When marker alignment is complete
                RobotCalibrationStates.ALIGN_ROBOT,  # Go back for next marker
                RobotCalibrationStates.ERROR,
                RobotCalibrationStates.SAMPLE_HEIGHT
            },

            RobotCalibrationStates.SAMPLE_HEIGHT:{
                RobotCalibrationStates.DONE,
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.DONE: {
                RobotCalibrationStates.ALIGN_ROBOT,  # Next marker
                RobotCalibrationStates.DONE,  # Final completion (all markers processed)
                RobotCalibrationStates.ERROR
            },

            RobotCalibrationStates.ERROR: {
                RobotCalibrationStates.ERROR,  # Allow staying in error
                RobotCalibrationStates.INITIALIZING,  # Full reset
            },
        }