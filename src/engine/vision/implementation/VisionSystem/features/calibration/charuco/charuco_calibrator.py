from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


class CharucoCalibrator:
    """
    Collects ChArUco corner detections across multiple frames and runs
    cv2.calibrateCamera to produce camera intrinsics.

    Typical usage::

        calibrator = CharucoCalibrator(detector.normal.board)
        for image, corners, ids in frames:
            calibrator.add_frame(image, corners, ids)
        rms, K, dist, rvecs, tvecs = calibrator.calibrate()
    """

    MIN_CORNERS_PER_FRAME = 4
    MIN_FRAMES = 5

    def __init__(self, board: cv2.aruco.CharucoBoard) -> None:
        self.board = board
        self._all_corners: list[np.ndarray] = []
        self._all_ids: list[np.ndarray] = []
        self._image_size: Optional[Tuple[int, int]] = None

    @property
    def frame_count(self) -> int:
        return len(self._all_corners)

    def add_frame(
        self,
        image: np.ndarray,
        charuco_corners: Optional[np.ndarray],
        charuco_ids: Optional[np.ndarray],
    ) -> bool:
        """
        Add one detection to the calibration set.
        Returns True if the frame was accepted (enough corners detected).
        """
        if image is None or charuco_corners is None or charuco_ids is None:
            return False
        if len(charuco_ids) < self.MIN_CORNERS_PER_FRAME:
            return False

        h, w = image.shape[:2]
        if self._image_size is None:
            self._image_size = (w, h)

        self._all_corners.append(charuco_corners)
        self._all_ids.append(charuco_ids)
        return True

    def clear(self) -> None:
        self._all_corners.clear()
        self._all_ids.clear()
        self._image_size = None

    def calibrate(self) -> Tuple[float, np.ndarray, np.ndarray, list, list]:
        """
        Run calibration on all collected frames.

        Returns:
            (rms, camera_matrix, dist_coeffs, rvecs, tvecs)

        Raises:
            RuntimeError if not enough valid frames.
        """
        if self._image_size is None or self.frame_count < self.MIN_FRAMES:
            raise RuntimeError(
                f"Need ≥ {self.MIN_FRAMES} frames, have {self.frame_count}."
            )

        chessboard_corners = self.board.getChessboardCorners()
        all_obj: list[np.ndarray] = []
        all_img: list[np.ndarray] = []

        for corners, ids in zip(self._all_corners, self._all_ids):
            if ids is None or corners is None or len(ids) < self.MIN_CORNERS_PER_FRAME:
                continue
            obj = chessboard_corners[ids.flatten()].reshape(-1, 1, 3).astype(np.float32)
            img = corners.reshape(-1, 1, 2).astype(np.float32)
            all_obj.append(obj)
            all_img.append(img)

        if len(all_obj) < self.MIN_FRAMES:
            raise RuntimeError(
                f"Only {len(all_obj)} frames passed corner filtering "
                f"(need ≥ {self.MIN_FRAMES})."
            )

        rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
            objectPoints=all_obj,
            imagePoints=all_img,
            imageSize=self._image_size,
            cameraMatrix=None,
            distCoeffs=None,
        )
        return rms, camera_matrix, dist_coeffs, rvecs, tvecs
