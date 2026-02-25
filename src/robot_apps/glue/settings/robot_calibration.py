

class RobotCalibrationConfig:
    def __init__(self, vision_system,
                 robot_service,
                 height_measuring_service,
                 required_ids,
                 z_target,
                 debug=False,
                 step_by_step=False,
                 live_visualization=False):
        self.vision_system = vision_system
        self.robot_service = robot_service
        self.height_measuring_service = height_measuring_service
        self.required_ids = required_ids
        self.z_target = z_target
        self.debug = debug
        self.step_by_step = step_by_step
        self.live_visualization = live_visualization
