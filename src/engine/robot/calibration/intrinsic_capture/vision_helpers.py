from __future__ import annotations

import logging
from typing import List, Tuple

import cv2
import numpy as np

from src.engine.robot.calibration.intrinsic_capture.types import (
    BoardDetection,
    BoardType,
    FeasibleRegion,
    ImageInfo,
    TargetRegion,
)

_logger = logging.getLogger(__name__)


def detect_board(
    frame: np.ndarray,
    pattern_size: Tuple[int, int],
    board_type: BoardType,
    square_size_mm: float = 25.0,
    marker_size_mm: float = 0.0,
    aruco_dict_id: int = cv2.aruco.DICT_4X4_250,
) -> BoardDetection:
    if board_type == BoardType.CHARUCO:
        mk_mm = marker_size_mm or square_size_mm * 0.75
        return detect_charuco_board(frame, pattern_size, square_size_mm, mk_mm, aruco_dict_id)
    return detect_chessboard(frame, pattern_size)


def detect_chessboard(frame: np.ndarray, pattern_size: Tuple[int, int]) -> BoardDetection:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
    if not found or corners is None or len(corners) == 0:
        return BoardDetection(found=False)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    corners = corners.reshape(-1, 2).astype(np.float32)
    return _board_detection_from_corners(corners)


def detect_charuco_board(
    frame: np.ndarray,
    pattern_size: Tuple[int, int],
    square_size_mm: float = 25.0,
    marker_size_mm: float = 0.0,
    aruco_dict_id: int = cv2.aruco.DICT_4X4_250,
) -> BoardDetection:
    from src.engine.vision.implementation.VisionSystem.features.calibration.charuco import (
        AutoCharucoBoardDetector,
    )

    if frame is None:
        return BoardDetection(found=False)

    mk_mm = marker_size_mm or square_size_mm * 0.75
    detector = AutoCharucoBoardDetector(
        squares_x=pattern_size[0],
        squares_y=pattern_size[1],
        square_length=square_size_mm,
        marker_length=mk_mm,
        dictionary_id=aruco_dict_id,
    )
    result = detector.detect(frame)
    n_markers = 0 if result.marker_ids is None else len(result.marker_ids)
    n_corners = 0 if result.charuco_ids is None else len(result.charuco_ids)
    if n_markers == 0:
        frame_h, frame_w = frame.shape[:2]
        _logger.info(
            "CharuCo: NO ArUco markers found in %dx%d frame [pattern=%s sq=%.1fmm mk=%.1fmm dict_id=%d]",
            frame_w, frame_h, pattern_size, square_size_mm, mk_mm, aruco_dict_id,
        )
        return BoardDetection(found=False)
    _logger.info("CharuCo: %d ArUco markers -> %d corners (need >=4) [mode=%s]", n_markers, n_corners, result.mode)
    if result.charuco_corners is None or n_corners < 4:
        return BoardDetection(found=False)
    corners = result.charuco_corners.reshape(-1, 2).astype(np.float32)
    return _board_detection_from_corners(corners)


def _board_detection_from_corners(corners: np.ndarray) -> BoardDetection:
    min_x = float(np.min(corners[:, 0]))
    min_y = float(np.min(corners[:, 1]))
    max_x = float(np.max(corners[:, 0]))
    max_y = float(np.max(corners[:, 1]))
    cx = float(np.mean(corners[:, 0]))
    cy = float(np.mean(corners[:, 1]))
    return BoardDetection(
        found=True,
        corners_px=corners,
        center_px=(cx, cy),
        bbox_px=(min_x, min_y, max_x, max_y),
        width_px=max_x - min_x,
        height_px=max_y - min_y,
    )


def compute_feasible_region(image: ImageInfo, det: BoardDetection, margin_px: float = 60.0) -> FeasibleRegion:
    if not det.found or det.width_px is None or det.height_px is None:
        raise ValueError("Board must be detected to compute feasible region.")
    half_w = det.width_px / 2.0
    half_h = det.height_px / 2.0
    min_cx = half_w + margin_px
    max_cx = image.width - half_w - margin_px
    min_cy = half_h + margin_px
    max_cy = image.height - half_h - margin_px
    if min_cx >= max_cx or min_cy >= max_cy:
        min_cx = half_w
        max_cx = image.width - half_w
        min_cy = half_h
        max_cy = image.height - half_h
    if min_cx >= max_cx or min_cy >= max_cy:
        raise RuntimeError(
            f"Board ({det.width_px:.0f}x{det.height_px:.0f} px) is larger than the image ({image.width}x{image.height} px)."
        )
    if max_cx - min_cx < 1:
        cx = (min_cx + max_cx) / 2.0
        min_cx = max_cx = cx
    if max_cy - min_cy < 1:
        cy = (min_cy + max_cy) / 2.0
        min_cy = max_cy = cy
    return FeasibleRegion(min_cx, min_cy, max_cx, max_cy)


def make_grid_regions(feasible: FeasibleRegion, grid_rows: int = 3, grid_cols: int = 3, tol_ratio: float = 0.25) -> List[TargetRegion]:
    xs = np.linspace(feasible.min_cx, feasible.max_cx, grid_cols)
    ys = np.linspace(feasible.min_cy, feasible.max_cy, grid_rows)
    cell_w = ((feasible.max_cx - feasible.min_cx) / max(grid_cols - 1, 1)) if grid_cols > 1 else (feasible.max_cx - feasible.min_cx)
    cell_h = ((feasible.max_cy - feasible.min_cy) / max(grid_rows - 1, 1)) if grid_rows > 1 else (feasible.max_cy - feasible.min_cy)
    tol_x = max(20.0, cell_w * tol_ratio)
    tol_y = max(20.0, cell_h * tol_ratio)
    regions: List[TargetRegion] = []
    for r, y in enumerate(ys):
        for c, x in enumerate(xs):
            regions.append(TargetRegion(name=f"r{r}_c{c}", center_px=(float(x), float(y)), tol_px=(float(tol_x), float(tol_y))))
    return regions
