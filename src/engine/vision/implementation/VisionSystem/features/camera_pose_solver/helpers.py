import logging
import numpy as np

_logger = logging.getLogger(__name__)

def print_pose_explained(pose_matrix):
    R = pose_matrix[:3, :3]
    t = pose_matrix[:3, 3]

    tx, ty, tz = t

    _logger.info("\n=== CAMERA POSE MATRIX EXPLAINED ===\n")

    _logger.info("4×4 Homogeneous Transformation Matrix (Camera → Chessboard):")

    _logger.info(pose_matrix)


    _logger.info("\n--- Translation (Camera origin relative to chessboard) ---")

    _logger.info(f"tx = {tx:.2f} mm   → Camera shift along chessboard X-axis")

    _logger.info(f"ty = {ty:.2f} mm   → Camera shift along chessboard Y-axis")

    _logger.info(f"tz = {tz:.2f} mm   → Camera height above chessboard")


    # Convert rotation matrix to Euler angles
    sy = (R[0, 0] ** 2 + R[1, 0] ** 2) ** 0.5
    singular = sy < 1e-6

    if not singular:
        roll = np.degrees(np.arctan2(R[2, 1], R[2, 2]))
        pitch = np.degrees(np.arctan2(-R[2, 0], sy))
        yaw = np.degrees(np.arctan2(R[1, 0], R[0, 0]))
    else:
        roll = np.degrees(np.arctan2(-R[1, 2], R[1, 1]))
        pitch = np.degrees(np.arctan2(-R[2, 0], sy))
        yaw = 0

    _logger.info("\n--- Rotation Matrix (Camera orientation) ---")

    _logger.info(R)


    _logger.info("\n--- Orientation (Euler angles in degrees) ---")

    _logger.info(f"Roll  (rotation around X) = {roll:.2f}°")

    _logger.info(f"Pitch (rotation around Y) = {pitch:.2f}°")

    _logger.info(f"Yaw   (rotation around Z) = {yaw:.2f}°")


    _logger.info("\nCamera looks DOWN the -Z axis of its coordinate vision_service.")

    _logger.info("Positive tz means chessboard is in front of the camera.\n")

    _logger.info("=====================================================\n")

