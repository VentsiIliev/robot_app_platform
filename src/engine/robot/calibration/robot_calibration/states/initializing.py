
import logging
_logger = logging.getLogger(__name__)

from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates

from src.engine.robot.calibration.robot_calibration.states.state_result import StateResult


def handle_initializing_state(frame_provider):
    handled = False
    if frame_provider is None:
        _logger.info("Waiting for camera to initialize...")
    else:
        handled= True
        _logger.info("System initialized")


    if handled:
        return StateResult(success=True,message="Initialization complete",next_state=RobotCalibrationStates.AXIS_MAPPING)
    else:
        return StateResult(success=False,message="Waiting for camera to initialize...",next_state=RobotCalibrationStates.INITIALIZING)