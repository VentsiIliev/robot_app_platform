import logging
import cv2
from matplotlib import pyplot as plt

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
from modules.VisionSystem.laser_detection.laser_calibration_service import LaserDetectionCalibration
from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService
from modules.VisionSystem.laser_detection.laser_detector import LaserDetector, LaserDetectionConfig
from modules.shared.tools.Laser import Laser
from core.services.vision.VisionService import VisionServiceSingleton
import time
import threading

_logger = logging.getLogger(__name__)

if __name__ == "__main__":


    def draw_crosshair_full_image(frame, color=(0, 255, 0), thickness=2):
        h, w = frame.shape[:2]
        cx, cy = w // 2, h // 2
        cv2.line(frame, (0, cy), (w - 1, cy), color, thickness)
        cv2.line(frame, (cx, 0), (cx, h - 1), color, thickness)

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


    def plot_calibration_curve(calibration_data):
        heights = [h for h, delta in calibration_data]
        deltas = [delta for h, delta in calibration_data]

        plt.figure(figsize=(8, 5))
        plt.plot(heights, deltas, marker='o', linestyle='-', color='b')
        plt.title("Laser Calibration Curve")
        plt.xlabel("Robot Height (mm)")
        plt.ylabel("Pixel Delta")
        plt.grid(True)
        plt.show()

    def main():
        vision_system = VisionServiceSingleton().get_instance()
        vision_system.contourDetection = False
        vision_system.get_camera_settings().set_brightness_auto(False)
        vision_system.camera.set_auto_exposure(False)
        threading.Thread(target=vision_system.run, daemon=True).start()

        robot_service = init_robot_service()

        config = LaserDetectionConfig()
        laser = Laser()
        laser_detector = LaserDetector(config)
        laser_service = LaserDetectionService(laser_detector, laser, vision_system)

        measuring_height = 343.112  # mm
        initial_position = [30,410, measuring_height, 180, 0, 0]  # X,Y,Z in mm and RX,RY,RZ in degrees
        laser_calibration = LaserDetectionCalibration(laser_service, robot_service)

        """MAKE SURE CAMERA IS INITIALIZED"""
        frame = vision_system.latest_frame
        while frame is None or frame.size == 0:
            _logger.info("Waiting for camera frame...")

            time.sleep(0.5)
            frame = vision_system.latest_frame

        _logger.info("Camera frame received. Starting laser calibration...")



        laser_calibration.calibrate(initial_position)
        laser_calibration.print_calibration_data()
        plot_calibration_curve(laser_calibration.calibration_data)

    main()
