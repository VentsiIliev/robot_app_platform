import json
import logging
from itertools import combinations
import numpy as np
import cv2

_logger = logging.getLogger(__name__)


def compute_avg_ppm(camera_points, robot_points):
    # List to store PPM values
    ppms = []
    cam_pts = camera_points
    rob_pts = robot_points
    # Compute PPM for each pair of points
    for i, j in combinations(range(len(cam_pts)), 2):
        # Distance in pixels
        dist_px = np.linalg.norm(cam_pts[i] - cam_pts[j])
        # Distance in mm
        dist_mm = np.linalg.norm(rob_pts[i] - rob_pts[j])
        # PPM for this pair
        ppms.append(dist_px / dist_mm)

    # Compute average PPM
    average_ppm = np.mean(ppms)

def test_calibration(homography_matrix, camera_points, robot_points, save_json_path=None):
        """
        Test a homography by comparing transformed camera points to robot points.
        Returns average error and transformed points in cv2 format (N, 1, 2).

        :param homography_matrix: 3x3 homography matrix
        :param camera_points: Nx2 array-like of camera points
        :param robot_points: Nx2 array-like of robot points
        :param save_json_path: Path to save JSON results (optional). `.json` appended if missing.
        :return: (average_error, transformed_points_cv2) where transformed_points_cv2 shape is (N, 1, 2)
        """
        # Normalize inputs
        cam_pts = np.asarray(camera_points, dtype=np.float32).reshape(-1, 2)
        rob_pts = np.asarray(robot_points, dtype=np.float32).reshape(-1, 2)

        compute_avg_ppm(cam_pts, rob_pts)

        # Compute transformed points in cv2 format (N, 1, 2)
        transformed_pts_cv2 = cv2.perspectiveTransform(cam_pts.reshape(-1, 1, 2), homography_matrix)  # shape (N,1,2)
        transformed_pts_flat = transformed_pts_cv2.reshape(-1, 2)  # for calculations/logging

        # Prepare data for logging and JSON
        results = []
        for i, (cam_pt, transformed, robot_pt) in enumerate(zip(cam_pts, transformed_pts_flat, rob_pts)):
            error = float(np.linalg.norm(transformed - robot_pt))

            _logger.debug(f"Point {i + 1}:")
            _logger.debug(f"  Camera point:      {cam_pt}")
            _logger.debug(f"  Transformed point: {transformed}")
            _logger.debug(f"  Robot point:       {robot_pt}")
            _logger.debug(f"  Error (mm):        {error:.3f}")

            results.append({
                "point": i + 1,
                "camera_point": [float(cam_pt[0]), float(cam_pt[1])],
                "transformed_point": [float(transformed[0]), float(transformed[1])],
                "robot_point": [float(robot_pt[0]), float(robot_pt[1])],
                "error_mm": error
            })

        # Compute average error
        errors = np.array([r["error_mm"] for r in results], dtype=np.float32)
        average_error = float(np.mean(errors)) if errors.size > 0 else 0.0
        _logger.debug(f"Average transformation error: {average_error} mm")


        # Save to JSON if path provided (ensure .json extension)
        if save_json_path:
            if not str(save_json_path).lower().endswith(".json"):
                save_json_path = f"{save_json_path}.json"
            json_data = {"calibration_points": results, "average_error_mm": average_error}
            with open(save_json_path, "w") as f:
                json.dump(json_data, f, indent=4)
            _logger.debug(f"Saved calibration results to {save_json_path}")

        # Return average error and transformed points in cv2 format (N, 1, 2)
        return average_error, transformed_pts_cv2

def compute_homography(camera_points_for_homography, robot_positions_for_calibration):
    # Sort by marker ID
    sorted_robot_items = sorted(robot_positions_for_calibration.items(), key=lambda x: x[0])
    sorted_camera_items = sorted(camera_points_for_homography.items(), key=lambda x: x[0])

    # Prepare corresponding points in sorted order
    robot_positions = [pos[:2] for _, pos in sorted_robot_items]
    camera_points = [pt for _, pt in sorted_camera_items]

    # Compute homography
    src_pts = np.array(camera_points, dtype=np.float32)
    dst_pts = np.array(robot_positions, dtype=np.float32)
    H_camera_center, status = cv2.findHomography(src_pts, dst_pts)
    return H_camera_center,status