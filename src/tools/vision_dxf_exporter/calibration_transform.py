from __future__ import annotations

import os

import cv2
import numpy as np

from src.engine.vision.homography_transformer import HomographyTransformer


class CameraPlaneCalibrationTransformer:
    """Map image pixels to chessboard-plane millimeters from camera calibration data."""

    def __init__(self, calibration_data_path: str) -> None:
        self._path = calibration_data_path
        self._camera_matrix = None
        self._dist_coeffs = None
        self._rotation = None
        self._translation = None
        self._load()

    def _load(self) -> None:
        try:
            data = np.load(self._path, allow_pickle=True)
            self._camera_matrix = np.asarray(data["camera_matrix"], dtype=float)
            self._dist_coeffs = np.asarray(data["dist_coeffs"], dtype=float)
            rvecs = data["rvecs"]
            tvecs = data["tvecs"]
            rvec = np.asarray(rvecs[0], dtype=float).reshape(3, 1)
            self._translation = np.asarray(tvecs[0], dtype=float).reshape(3)
            self._rotation, _ = cv2.Rodrigues(rvec)
        except Exception:
            self._camera_matrix = None
            self._dist_coeffs = None
            self._rotation = None
            self._translation = None

    def is_available(self) -> bool:
        return self._camera_matrix is not None and self._rotation is not None and self._translation is not None

    def reload(self) -> bool:
        self._load()
        return self.is_available()

    def transform(self, x: float, y: float) -> tuple[float, float]:
        if not self.is_available():
            raise RuntimeError("Camera-plane calibration data is not available")

        undistorted = cv2.undistortPoints(
            np.asarray([[[float(x), float(y)]]], dtype=np.float64),
            self._camera_matrix,
            self._dist_coeffs,
        )
        ray = np.asarray([float(undistorted[0, 0, 0]), float(undistorted[0, 0, 1]), 1.0], dtype=float)
        r1 = self._rotation[:, 0]
        r2 = self._rotation[:, 1]
        system = np.column_stack([r1, r2, -ray])
        solution = np.linalg.solve(system, -self._translation)
        return float(solution[0]), float(solution[1])


class CompositeCalibrationTransformer:
    """Prefer robot homography, then fall back to camera-plane calibration."""

    def __init__(self, robot_homography_path: str, calibration_data_path: str) -> None:
        self._robot = HomographyTransformer(robot_homography_path)
        self._camera_plane = CameraPlaneCalibrationTransformer(calibration_data_path)

    def is_available(self) -> bool:
        return self._active() is not None

    def reload(self) -> bool:
        self._robot.reload()
        self._camera_plane.reload()
        return self.is_available()

    def transform(self, x: float, y: float) -> tuple[float, float]:
        active = self._active()
        if active is None:
            raise RuntimeError(
                "No calibrated millimeter transform is available. Run calibration or provide cameraToRobotMatrix_camera_center.npy."
            )
        return active.transform(x, y)

    def source_label(self) -> str:
        if self._robot.is_available():
            return "robot homography"
        if self._camera_plane.is_available():
            return "camera plane calibration"
        return "unavailable"

    def _active(self):
        if self._robot.is_available():
            return self._robot
        if self._camera_plane.is_available():
            return self._camera_plane
        return None


def build_calibration_transformer(vision_service) -> CompositeCalibrationTransformer:
    matrix_path = str(vision_service.camera_to_robot_matrix_path)
    calibration_path = os.path.join(os.path.dirname(matrix_path), "calibration_data.npz")
    return CompositeCalibrationTransformer(matrix_path, calibration_path)
