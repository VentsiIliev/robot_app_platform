class RobotTopics:
    STATE        = "robot/state"
    POSITION     = "robot/position"
    VELOCITY     = "robot/velocity"
    ACCELERATION = "robot/acceleration"


class RobotCalibrationTopics:
    """EVENTS ARE ONLY USED FOR PROVIDING FEEDBACK TO THE USER"""
    """DO NOT USED FOR COMMANDS !!!"""
    ROBOT_CALIBRATION_LOG = "robot/calibration/log"
    ROBOT_CALIBRATION_START = "robot/calibration/start"
    ROBOT_CALIBRATION_STOP = "robot/calibration/stop"
    ROBOT_CALIBRATION_IMAGE = "robot/calibration/image"
    ROBOT_STATE = "robot/state"  # example message -> {"state": self.robotState,"position": self.position, "speed": self.velocity, "accel": self.acceleration}