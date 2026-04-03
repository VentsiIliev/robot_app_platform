from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass
class DetectionResult:
    mode: str
    charuco_corners: Optional[np.ndarray]
    charuco_ids: Optional[np.ndarray]
    marker_corners: Tuple[np.ndarray, ...]
    marker_ids: Optional[np.ndarray]
    vis: np.ndarray
    rvec: Optional[np.ndarray]
    tvec: Optional[np.ndarray]


class CharucoBoardDetector:
    """Single ChArUco detector for one board convention (normal or legacy)."""

    def __init__(
        self,
        squares_x: int = 5,
        squares_y: int = 6,
        square_length: float = 0.04,
        marker_length: float = 0.02,
        dictionary_id: int = cv2.aruco.DICT_4X4_50,
        legacy_pattern: bool = False,
    ) -> None:
        self.squares_x = squares_x
        self.squares_y = squares_y
        self.square_length = square_length
        self.marker_length = marker_length
        self.dictionary_id = dictionary_id
        self.legacy_pattern = legacy_pattern

        self.dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
        self.board = cv2.aruco.CharucoBoard(
            (squares_x, squares_y),
            square_length,
            marker_length,
            self.dictionary,
        )

        if legacy_pattern:
            if hasattr(self.board, "setLegacyPattern"):
                self.board.setLegacyPattern(True)
            else:
                raise RuntimeError(
                    "This OpenCV build does not support setLegacyPattern(). "
                    "Install/upgrade opencv-contrib-python."
                )

        self.detector = cv2.aruco.CharucoDetector(self.board)

    def generate_board_image(
        self,
        out_size: Tuple[int, int] = (900, 1100),
        margin_size: int = 20,
        border_bits: int = 1,
    ) -> np.ndarray:
        return self.board.generateImage(
            out_size,
            marginSize=margin_size,
            borderBits=border_bits,
        )

    def detect_raw(self, image: np.ndarray):
        if image is None:
            raise ValueError("Input image is None")
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        return self.detector.detectBoard(gray)


class AutoCharucoBoardDetector:
    """
    Try new convention first, then legacy convention — keep the better result.
    Also estimates board pose and draws coordinate axes when enough ChArUco
    corners are detected.
    """

    def __init__(
        self,
        squares_x: int = 5,
        squares_y: int = 6,
        square_length: float = 0.04,
        marker_length: float = 0.02,
        dictionary_id: int = cv2.aruco.DICT_4X4_50,
    ) -> None:
        self.normal = CharucoBoardDetector(
            squares_x=squares_x,
            squares_y=squares_y,
            square_length=square_length,
            marker_length=marker_length,
            dictionary_id=dictionary_id,
            legacy_pattern=False,
        )
        self.legacy = CharucoBoardDetector(
            squares_x=squares_x,
            squares_y=squares_y,
            square_length=square_length,
            marker_length=marker_length,
            dictionary_id=dictionary_id,
            legacy_pattern=True,
        )
        self.square_length = square_length

    @staticmethod
    def _build_demo_camera_matrix(image_shape: Tuple[int, int, int]) -> np.ndarray:
        h, w = image_shape[:2]
        return np.array(
            [[float(w), 0.0, w / 2.0],
             [0.0, float(w), h / 2.0],
             [0.0, 0.0, 1.0]],
            dtype=np.float32,
        )

    @staticmethod
    def _estimate_pose(
        board,
        charuco_corners: Optional[np.ndarray],
        charuco_ids: Optional[np.ndarray],
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        if charuco_ids is None or charuco_corners is None or len(charuco_ids) < 6:
            return None, None
        try:
            obj_points, img_points = board.matchImagePoints(charuco_corners, charuco_ids)
        except Exception:
            return None, None
        if obj_points is None or img_points is None:
            return None, None
        if len(obj_points) < 6:
            return None, None
        ok, rvec, tvec = cv2.solvePnP(
            obj_points, img_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )
        return (rvec, tvec) if ok else (None, None)

    def _make_result(
        self,
        mode: str,
        board_detector: CharucoBoardDetector,
        image: np.ndarray,
        charuco_corners,
        charuco_ids,
        marker_corners,
        marker_ids,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None,
    ) -> DetectionResult:
        vis = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) if image.ndim == 2 else image.copy()

        if marker_ids is not None and len(marker_ids) > 0:
            cv2.aruco.drawDetectedMarkers(vis, marker_corners, marker_ids)
        if charuco_ids is not None and len(charuco_ids) > 0:
            cv2.aruco.drawDetectedCornersCharuco(vis, charuco_corners, charuco_ids, (0, 255, 0))

        K    = camera_matrix if camera_matrix is not None else self._build_demo_camera_matrix(vis.shape)
        dist = dist_coeffs   if dist_coeffs   is not None else np.zeros((5, 1), dtype=np.float32)

        rvec, tvec = self._estimate_pose(board_detector.board, charuco_corners, charuco_ids, K, dist)
        if rvec is not None and tvec is not None:
            cv2.drawFrameAxes(vis, K, dist, rvec, tvec, self.square_length * 2.0, 2)

        return DetectionResult(
            mode=mode,
            charuco_corners=charuco_corners,
            charuco_ids=charuco_ids,
            marker_corners=marker_corners,
            marker_ids=marker_ids,
            vis=vis,
            rvec=rvec,
            tvec=tvec,
        )

    def detect(
        self,
        image: np.ndarray,
        camera_matrix: Optional[np.ndarray] = None,
        dist_coeffs: Optional[np.ndarray] = None,
    ) -> DetectionResult:
        """
        Detect ChArUco corners in *image*.

        Optionally pass *camera_matrix* and *dist_coeffs* so that the pose
        estimate and axis overlay use real intrinsics instead of the demo
        approximation.
        """
        normal_corners, normal_ids, normal_mc, normal_mi = self.normal.detect_raw(image)
        legacy_corners, legacy_ids, legacy_mc, legacy_mi = self.legacy.detect_raw(image)

        normal_score = 0 if normal_ids is None else len(normal_ids)
        legacy_score = 0 if legacy_ids is None else len(legacy_ids)

        if legacy_score > normal_score:
            return self._make_result(
                "legacy", self.legacy, image,
                legacy_corners, legacy_ids, legacy_mc, legacy_mi,
                camera_matrix, dist_coeffs,
            )
        return self._make_result(
            "normal", self.normal, image,
            normal_corners, normal_ids, normal_mc, normal_mi,
            camera_matrix, dist_coeffs,
        )
