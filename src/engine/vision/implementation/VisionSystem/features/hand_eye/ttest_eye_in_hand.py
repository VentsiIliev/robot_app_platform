import logging
#!/usr/bin/env python3
"""
chessboard_to_robot_fixed.y_pixels

Detects chessboard in camera feed, computes 3D chessboard points,
and transforms them to robot coordinates using hand-eye calibration.
"""

import cv2
import numpy as np
import time
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

_logger = logging.getLogger(__name__)

# ==== CONFIG ====
USE_CHESSBOARD = True
BOARD_SIZE = (17, 11)
SQUARE_SIZE = 15.0  # mm

# Prepare 3D object points in chessboard frame (Z=0)
objp = np.zeros((BOARD_SIZE[0]*BOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.indices(BOARD_SIZE).T.reshape(-1,2) * SQUARE_SIZE

def main():
    ApplicationContext.set_current_application(ApplicationType.GLUE_DISPENSING)

    # Load hand-eye calibration matrix
    T_cam_robot = np.load("cameraToRobotMatrix.npy")
    _logger.info("Loaded T_cam_robot:\n", T_cam_robot)


    # Initialize vision service
    vs = VisionServiceSingleton().get_instance()
    vs.contourDetection = False
    threading.Thread(target=vs.run, daemon=True).start()

    # Initialize robot service
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

    # Optional: move robot to calibration position
    robot_service.move_to_calibration_position()

    cv2.namedWindow("Camera Feed", cv2.WINDOW_NORMAL)
    _logger.info("Press ESC to exit. Detecting chessboard and transforming corners to robot frame...")


    try:
        while True:
            frame = vs.latest_frame
            if frame is None:
                time.sleep(0.01)
                continue

            display = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, BOARD_SIZE)

            if found:
                cv2.drawChessboardCorners(display, BOARD_SIZE, corners, found)
                corners_sub = cv2.cornerSubPix(
                    gray, corners, (11,11), (-1,-1),
                    criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1)
                )

                # Compute 3D pose of chessboard in camera frame
                retval, rvec, tvec = cv2.solvePnP(objp, corners_sub, vs.cameraMatrix, vs.cameraDist)
                R_cam, _ = cv2.Rodrigues(rvec)
                t_cam = tvec.reshape(3,1)

                # Transform each 3D chessboard point to robot frame
                for idx, p_obj in enumerate(objp):
                    p_cam_coord = R_cam @ p_obj.reshape(3,1) + t_cam
                    p_cam_homog = np.vstack((p_cam_coord, [[1]]))
                    p_robot = T_cam_robot @ p_cam_homog
                    _logger.info(f"Corner #{idx+1}: Robot coords = {p_robot[:3].flatten()}")


            cv2.imshow("Camera Feed", display)
            key = cv2.waitKey(1)
            if key == 27:  # ESC
                break
            time.sleep(0.01)

    finally:
        cv2.destroyAllWindows()
        _logger.info("Exiting...")


if __name__ == "__main__":
    main()
