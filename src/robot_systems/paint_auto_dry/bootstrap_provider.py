from src.robot_systems.paint.bootstrap_provider import PaintBootstrapProvider
from src.robot_systems.paint.paint_robot_system import AutomaticDryerPaintRobotSystem
from src.robot_systems.robot_system_bootstrap_provider import RobotSystemBootstrapProvider


def create_bootstrap_provider() -> RobotSystemBootstrapProvider:
    return PaintBootstrapProvider(AutomaticDryerPaintRobotSystem)
