import threading

from core.application import ApplicationContext
from core.application.ApplicationContext import get_core_settings_path
from core.application.interfaces.application_settings_interface import ApplicationSettingsRegistry
from core.base_robot_application import ApplicationType
from core.model.robot import FairinoRobot
from core.model.robot.robot_types import RobotType
from core.services.robot_service.impl.RobotStateManager import RobotStateManager
from core.services.robot_service.impl.base_robot_service import RobotService
from core.services.robot_service.impl.robot_monitor.robot_monitor_factory import RobotMonitorFactory
from core.services.settings.SettingsService import SettingsService
from core.services.vision.VisionService import VisionServiceSingleton


def init_vision_service():
    vision_system = VisionServiceSingleton().get_instance()
    vision_system.contourDetection = False
    vision_system.get_camera_settings().set_brightness_auto(False)
    vision_system.camera.set_auto_exposure(False)
    vision_system.camera.set_auto_exposure(False)

    threading.Thread(target=vision_system.run, daemon=True).start()
    return vision_system

def init_robot_service():
    ApplicationContext.set_current_application(ApplicationType.GLUE_DISPENSING)
    robot_settings_paths = {
        "camera": get_core_settings_path("camera_settings.json", create_if_missing=True),
        "robot_config": get_core_settings_path("robot_config.json", create_if_missing=True),
        "robot_calibration_settings": get_core_settings_path("robot_calibration_settings.json",
                                                             create_if_missing=True),
    }
    settings_registry = ApplicationSettingsRegistry()
    settings_service = SettingsService(settings_file_paths=robot_settings_paths,
                                       settings_registry=settings_registry)
    robot = FairinoRobot(ip=settings_service.get_robot_config().robot_ip)
    robot_monitor = RobotMonitorFactory.create_monitor(RobotType.FAIRINO,
                                                       settings_service.get_robot_config().robot_ip,
                                                       robot,
                                                       cycle_time=0.03)
    robot_state_manager = RobotStateManager(robot_monitor)
    robot_service = RobotService(robot=robot, settings_service=settings_service,
                                 robot_state_manager=robot_state_manager)

    return robot_service