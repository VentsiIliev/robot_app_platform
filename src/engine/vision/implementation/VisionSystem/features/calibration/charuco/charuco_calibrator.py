from __future__ import annotations

import logging
from typing import Optional, Tuple

import cv2
import numpy as np

_logger = logging.getLogger(__name__)


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

    MIN_CORNERS_PER_FRAME = 6
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

        corners, ids, reason = self._normalise_and_validate_detection(
            charuco_corners,
            charuco_ids,
        )
        if corners is None or ids is None:
            _logger.debug("Rejecting ChArUco calibration frame: %s", reason)
            return False

        h, w = image.shape[:2]
        if self._image_size is None:
            self._image_size = (w, h)

        self._all_corners.append(corners)
        self._all_ids.append(ids)
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

        all_obj: list[np.ndarray] = []
        all_img: list[np.ndarray] = []
        rejected = 0

        for corners, ids in zip(self._all_corners, self._all_ids):
            corners, ids, reason = self._normalise_and_validate_detection(corners, ids)
            if corners is None or ids is None:
                rejected += 1
                _logger.debug("Rejecting ChArUco calibration frame before solve: %s", reason)
                continue
            obj = self.board.getChessboardCorners()[ids.flatten()].reshape(-1, 1, 3).astype(np.float32)
            img = corners.reshape(-1, 1, 2).astype(np.float32)
            all_obj.append(obj)
            all_img.append(img)

        if rejected:
            _logger.info("Rejected %d degenerate ChArUco calibration frames before solve", rejected)

        if len(all_obj) < self.MIN_FRAMES:
            raise RuntimeError(
                f"Only {len(all_obj)} frames passed corner filtering "
                f"(need ≥ {self.MIN_FRAMES})."
            )

        try:
            rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                objectPoints=all_obj,
                imagePoints=all_img,
                imageSize=self._image_size,
                cameraMatrix=None,
                distCoeffs=None,
            )
        except cv2.error as exc:
            raise RuntimeError(f"OpenCV ChArUco calibration failed after filtering: {exc}") from exc
        return rms, camera_matrix, dist_coeffs, rvecs, tvecs

    def _normalise_and_validate_detection(
        self,
        charuco_corners: Optional[np.ndarray],
        charuco_ids: Optional[np.ndarray],
    ) -> tuple[np.ndarray | None, np.ndarray | None, str]:
        if charuco_corners is None or charuco_ids is None:
            return None, None, "missing corners or ids"

        ids = np.asarray(charuco_ids, dtype=np.int32).reshape(-1)
        corners = np.asarray(charuco_corners, dtype=np.float32).reshape(-1, 2)
        if ids.size != corners.shape[0]:
            return None, None, f"ids/corners length mismatch ({ids.size} ids, {corners.shape[0]} corners)"
        if ids.size < self.MIN_CORNERS_PER_FRAME:
            return None, None, f"too few corners ({ids.size}, need {self.MIN_CORNERS_PER_FRAME})"

        board_corners = np.asarray(self.board.getChessboardCorners(), dtype=np.float32)
        valid_mask = (ids >= 0) & (ids < len(board_corners))
        if not np.all(valid_mask):
            ids = ids[valid_mask]
            corners = corners[valid_mask]
        if ids.size < self.MIN_CORNERS_PER_FRAME:
            return None, None, "too few in-board corners after filtering"

        unique_ids, unique_indices = np.unique(ids, return_index=True)
        if unique_ids.size != ids.size:
            ids = ids[np.sort(unique_indices)]
            corners = corners[np.sort(unique_indices)]
        if ids.size < self.MIN_CORNERS_PER_FRAME:
            return None, None, "too few unique corners after duplicate filtering"

        obj_xy = board_corners[ids, :2].astype(np.float32)
        if not self._has_2d_spread(obj_xy):
            return None, None, "object points are degenerate or nearly collinear"
        if not self._has_2d_spread(corners):
            return None, None, "image points are degenerate or nearly collinear"

        return corners.reshape(-1, 1, 2), ids.reshape(-1, 1), "ok"

    @staticmethod
    def _has_2d_spread(points: np.ndarray) -> bool:
        pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
        if pts.shape[0] < 3:
            return False
        centered = pts - np.mean(pts, axis=0)
        _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
        if singular_values.size < 2 or singular_values[1] <= 1e-6:
            return False
        hull = cv2.convexHull(pts.reshape(-1, 1, 2))
        return float(cv2.contourArea(hull)) > 1e-3
