import logging
#!/usr/bin/env python3
"""
eye_in_hand_calibration_absolute_safe_fixed.y_pixels

Fixed eye-in-hand calibration:
- Proper Euler -> rotation matrix conversion
- Collects hand-eye samples and computes T_cam_robot
"""

import threading
import time
import cv2
import numpy as np

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
MIN_Z = 300  # minimum Z to avoid collisions

# Absolute predefined poses (from recorded robot positions)
POSES = [
    [-19.961, 332.220, 819.139, 179.872, 0.021, 0.000],
    [296.946, 426.645, 494.714, 166.919, 12.173, -22.760],
    [39.719, 282.852, 502.540, -168.716, 6.191, -3.811],
    [-31.286, 595.141, 461.606, 153.230, -0.117, -6.009],
    [-356.514, 453.000, 406.893, 167.567, -31.560, 10.675],
    [-21.758, 551.845, 528.024, 166.311, -20.532, -72.128],
    [-208.610, 593.086, 450.321, 148.397, -10.375, 35.123],
    [255.291, 524.126, 486.553, 159.341, 5.838, -34.464],
    [-39.079, 384.350, 422.272, 178.944, 3.165, -2.582],
]

# Prepare object points for chessboard
objp = np.zeros((BOARD_SIZE[0]*BOARD_SIZE[1], 3), np.float32)
objp[:, :2] = np.indices(BOARD_SIZE).T.reshape(-1,2) * SQUARE_SIZE

# ==== STORAGE ====
R_robot, t_robot = [], []
R_cam, t_cam = [], []

# ==== HELPER FUNCTIONS ====
def deg2rad(deg):
    return np.array(deg) * np.pi / 180

def wrap_angle_180(angle):
    return (angle + 180) % 360 - 180

def enforce_limits(pose):
    x, y, z, rx, ry, rz = pose
    z = max(z, MIN_Z)
    rx, ry, rz = wrap_angle_180(rx), wrap_angle_180(ry), wrap_angle_180(rz)
    return [x, y, z, rx, ry, rz]

def euler_to_rotmat(rx, ry, rz):
    """Convert Euler angles (degrees) to rotation matrix"""
    rx, ry, rz = np.deg2rad([rx, ry, rz])
    Rx = np.array([[1,0,0],
                   [0,np.cos(rx), -np.sin(rx)],
                   [0,np.sin(rx), np.cos(rx)]])
    Ry = np.array([[np.cos(ry),0,np.sin(ry)],
                   [0,1,0],
                   [-np.sin(ry),0,np.cos(ry)]])
    Rz = np.array([[np.cos(rz), -np.sin(rz),0],
                   [np.sin(rz), np.cos(rz),0],
                   [0,0,1]])
    return Rz @ Ry @ Rx  # ZYX order

def tcp_to_matrix(tcp_pose):
    x, y, z, rx, ry, rz = tcp_pose
    R = euler_to_rotmat(rx, ry, rz)
    T = np.eye(4, dtype=np.float64)
    T[:3,:3] = R
    T[:3,3] = np.array([x, y, z])
    return T

def show_camera(vs, stop_event):
    cv2.namedWindow("Camera Feed", cv2.WINDOW_NORMAL)
    while not stop_event.is_set():
        frame = vs.latest_frame
        if frame is not None and frame.size > 0:
            display = frame.copy()
            if USE_CHESSBOARD:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                found, corners = cv2.findChessboardCorners(gray, BOARD_SIZE)
                if found:
                    cv2.drawChessboardCorners(display, BOARD_SIZE, corners, found)
            cv2.imshow("Camera Feed", display)
            cv2.waitKey(1)
    cv2.destroyAllWindows()

def move_robot_to_pose(robot_service:RobotService, pose):
    pose = enforce_limits(pose)
    config = robot_service.robot_config
    tool = config.robot_tool
    user = config.robot_user
    robot_service.move_to_position(position=pose, tool=tool, workpiece=user,
                                   velocity=40, acceleration=10, waitToReachPosition=True)
    time.sleep(1.5)

def wait_for_chessboard(vs, timeout=15):
    start_time = time.time()
    while True:
        frame = vs.latest_frame
        if frame is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            found, corners = cv2.findChessboardCorners(gray, BOARD_SIZE)
            if found:
                return corners, frame
        if time.time() - start_time > timeout:
            _logger.warning("[WARN] Chessboard not detected within timeout.")

            return None, None
        time.sleep(0.1)

def collect_hand_eye_samples(robot_service: RobotService, vs):
    camera_matrix = vs.cameraMatrix
    dist_coeffs = vs.cameraDist

    for idx, pose in enumerate(POSES):
        _logger.info(f"\nMoving to pose {idx+1}/{len(POSES)}: {pose}")

        move_robot_to_pose(robot_service, pose)

        corners, frame = wait_for_chessboard(vs)
        if corners is None:
            _logger.warning("[WARN] Skipping pose due to no chessboard detection.")

            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cv2.cornerSubPix(gray, corners, (11,11), (-1,-1),
                         criteria=(cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,30,0.1))
        retval, rvec, tvec = cv2.solvePnP(objp, corners, camera_matrix, dist_coeffs)
        R_c,_ = cv2.Rodrigues(rvec)
        t_c = tvec.reshape(3,1)

        R_cam.append(R_c)
        t_cam.append(t_c)

        T_robot = tcp_to_matrix(pose)
        R_r = T_robot[:3,:3]
        t_r = T_robot[:3,3].reshape(3,1)
        R_robot.append(R_r)
        t_robot.append(t_r)

        _logger.info(f"[OK] Captured pose {idx+1}/{len(POSES)}")


    _logger.info("\n[✓] Finished collecting all samples!")


def compute_hand_eye():
    R_cam_robot, t_cam_robot = cv2.calibrateHandEye(
        R_robot, t_robot, R_cam, t_cam, method=cv2.CALIB_HAND_EYE_TSAI
    )
    T_cam_robot = np.eye(4)
    T_cam_robot[:3,:3] = R_cam_robot
    T_cam_robot[:3,3] = t_cam_robot.reshape(3)
    return T_cam_robot

def run_hand_eye():
    ApplicationContext.set_current_application(ApplicationType.GLUE_DISPENSING)

    vs = VisionServiceSingleton().get_instance()
    vs.contourDetection = False
    threading.Thread(target=vs.run, daemon=True).start()

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

    stop_event = threading.Event()
    cam_thread = threading.Thread(target=show_camera, args=(vs, stop_event), daemon=True)
    cam_thread.start()

    collect_hand_eye_samples(robot_service, vs)

    stop_event.set()
    cam_thread.join()

    T = compute_hand_eye()
    _logger.info("\n====================================")

    _logger.info("  HAND-EYE ROBOT_CALIBRATION RESULT")

    _logger.info("====================================")

    _logger.info("T_cam_robot =\n", T)

    np.save("cameraToRobotMatrix.npy", T)
    _logger.info("\nSaved as cameraToRobotMatrix.npy")


if __name__ == "__main__":
    run_hand_eye()
