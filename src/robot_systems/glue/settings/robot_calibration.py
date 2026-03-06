from src.engine.robot.interfaces import IRobotService
from src.engine.vision import IVisionService


class RobotCalibrationConfig:
    def __init__(self,
                 vision_service: IVisionService,
                 robot_service: IRobotService,
                 navigation_service,
                 height_measuring_service,
                 required_ids,
                 z_target,
                 robot_tool: int = 0,
                 robot_user: int = 0,
                 debug=False,
                 step_by_step=False,
                 live_visualization=False):
        self.vision_service = vision_service
        self.robot_service = robot_service
        self.navigation_service = navigation_service
        self.height_measuring_service = height_measuring_service
        self.required_ids = required_ids
        self.z_target = z_target
        self.robot_tool = robot_tool
        self.robot_user = robot_user
        self.debug = debug
        self.step_by_step = step_by_step
        self.live_visualization = live_visualization