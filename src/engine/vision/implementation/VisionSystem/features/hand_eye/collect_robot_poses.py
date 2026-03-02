import logging
#!/usr/bin/env python3
import time
import cv2

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
from modules.VisionSystem.laser_detection.laser_detection_service import LaserDetectionService, LaserDetectionConfig
from modules.shared.tools.Laser import Laser

_logger = logging.getLogger(__name__)

USE_CHESSBOARD = True
BOARD_SIZE = (17, 11)

def main():
    ApplicationContext.set_current_application(ApplicationType.GLUE_DISPENSING)

    # Vision service
    vs = VisionServiceSingleton().get_instance()
    vs.contourDetection = False
    # Only start the capture thread; do NOT call imshow there
    import threading
    threading.Thread(target=vs.run, daemon=True).start()

    # Robot service
    robot_settings_paths = {
        "camera": get_core_settings_path("camera_settings.json", create_if_missing=True),
        "robot_config": get_core_settings_path("robot_config.json", create_if_missing=True),
        "robot_calibration_settings": get_core_settings_path("robot_calibration_settings.json", create_if_missing=True),
    }
    settings_registry = ApplicationSettingsRegistry()
    settings_service = SettingsService(settings_file_paths=robot_settings_paths, settings_registry=settings_registry)
    robot = FairinoRobot(ip=settings_service.get_robot_config().robot_ip)
    robot_monitor = RobotMonitorFactory.create_monitor(RobotType.FAIRINO,
                                                       settings_service.get_robot_config().robot_ip,
                                                       robot,
                                                       cycle_time=0.03)
    robot_state_manager = RobotStateManager(robot_monitor)
    robot_service = RobotService(robot=robot, settings_service=settings_service,
                                 robot_state_manager=robot_state_manager)
    robot_service.move_to_calibration_position()

    positions = []
    _logger.info("Press SPACE to capture the current robot pose. Press ESC to finish.")


    config = LaserDetectionConfig()
    lds = LaserDetectionService(config,Laser())
    cv2.namedWindow("Camera Feed", cv2.WINDOW_NORMAL)

    while True:
        frame = vs.latest_frame
        if frame is not None and frame.size > 0:
            display = frame.copy()
            if USE_CHESSBOARD:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                found, corners = cv2.findChessboardCorners(gray, BOARD_SIZE)
                if found:
                    cv2.drawChessboardCorners(display, BOARD_SIZE, corners, found)
            cv2.imshow("Camera Feed", display)
        else:
            # Optional: only print once or use a counter to avoid flooding console
            _logger.info("Waiting for camera frame...")

            time.sleep(0.1)
            continue

        key = cv2.waitKey(1) & 0xFF
        if key == 32:  # SPACE
            pose = robot_service.get_current_position()
            positions.append(pose)
            _logger.info(f"[OK] Captured pose #{len(positions)}: {pose}")

        elif key == 27:  # ESC
            _logger.info("Finished capturing poses.")

            break

    cv2.destroyAllWindows()

    # Save poses to file
    with open("robot_poses.txt", "w") as f:
        for pose in positions:
            f.write(", ".join([f"{p:.6f}" for p in pose]) + "\n")
    _logger.info(f"Saved {len(positions)} poses to robot_poses.txt")


if __name__ == "__main__":
    main()
