from src.engine.robot.interfaces import IRobotService
from src.engine.vision import IVisionService


class AdaptiveMovementConfig:
    def __init__(self, min_step_mm, max_step_mm, target_error_mm, max_error_ref, k, derivative_scaling):
        self.min_step_mm = min_step_mm  # minimum movement (for very small errors)
        self.max_step_mm = max_step_mm  # maximum movement for very large misalignment's
        self.target_error_mm = target_error_mm  # desired error to reach
        self.max_error_ref = max_error_ref  # error at which we reach max step
        self.k = k  # responsiveness (1.0 = smooth, 2.0 = faster reaction)
        self.derivative_scaling = derivative_scaling  # how strongly derivative term reduces step

    def to_dict(self):
        return {
            "min_step_mm": self.min_step_mm,
            "max_step_mm": self.max_step_mm,
            "target_error_mm": self.target_error_mm,
            "max_error_ref": self.max_error_ref,
            "k": self.k,
            "derivative_scaling": self.derivative_scaling
        }


class RobotCalibrationEventsConfig:
    def __init__(self, broker,
                 calibration_start_topic,
                 calibration_stop_topic,
                 calibration_image_topic,
                 calibration_log_topic):
        self.broker = broker
        self.calibration_start_topic = calibration_start_topic
        self.calibration_stop_topic = calibration_stop_topic
        self.calibration_image_topic = calibration_image_topic
        self.calibration_log_topic = calibration_log_topic

    def to_dict(self):
        return {
            "broker": self.broker,
            "calibration_start_topic": self.calibration_start_topic,
            "calibration_stop_topic": self.calibration_stop_topic,
            "calibration_image_topic": self.calibration_image_topic,
            "calibration_log_topic": self.calibration_log_topic
        }

class RobotCalibrationConfig:
    def __init__(self, vision_service, robot_service, navigation_service,
                 height_measuring_service, required_ids, z_target,
                 robot_tool, robot_user,
                 velocity: int = 30, acceleration: int = 10,
                 run_height_measurement: bool = True,
                 settings_service=None,
                 calibration_settings_key: str | None = None,
                 robot_config=None,
                 robot_config_key: str | None = None,
                 camera_tcp_offset_config=None,
                 axis_mapping_config=None,
                 debug=False, step_by_step=False, live_visualization=False,
                 use_marker_centre: bool = False,
                 use_ransac: bool = False,
                 perspective_matrix=None):
        self.vision_service = vision_service
        self.robot_service = robot_service
        self.robot_tool = robot_tool
        self.robot_user = robot_user
        self.velocity = velocity
        self.acceleration = acceleration
        self.run_height_measurement = run_height_measurement
        self.settings_service = settings_service
        self.calibration_settings_key = calibration_settings_key
        self.robot_config = robot_config
        self.robot_config_key = robot_config_key
        self.camera_tcp_offset_config = camera_tcp_offset_config
        self.navigation_service = navigation_service
        self.height_measuring_service = height_measuring_service
        self.required_ids = required_ids
        self.z_target = z_target
        self.axis_mapping_config = axis_mapping_config
        self.debug = debug
        self.step_by_step = step_by_step
        self.live_visualization = live_visualization
        # use mean of all 4 marker corners (rotation-invariant) instead of top-left corner
        self.use_marker_centre = use_marker_centre
        # use RANSAC outlier rejection in findHomography instead of plain DLT
        self.use_ransac = use_ransac
        # perspective matrix to correct detected pixel coordinates (None = no correction)
        self.perspective_matrix = perspective_matrix
