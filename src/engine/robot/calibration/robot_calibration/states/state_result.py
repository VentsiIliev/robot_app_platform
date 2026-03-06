from src.engine.robot.calibration.robot_calibration.states.robot_calibration_states import RobotCalibrationStates


class StateResult:
    def __init__(self, success: bool, message: str = "", data: dict = None,next_state: RobotCalibrationStates = None):
        self.success = success
        self.message = message
        self.data = data
        self.next_state = next_state