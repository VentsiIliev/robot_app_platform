from __future__ import annotations

import math
from typing import List, NamedTuple, Optional, Tuple

import cv2
import numpy as np


class BoardInfo(NamedTuple):
    cx: float
    cy: float
    bbox_w: float
    bbox_h: float
    area: float


def euler_to_rotmat(rx_deg: float, ry_deg: float, rz_deg: float) -> np.ndarray:
    """ZYX convention: Rz @ Ry @ Rx — matches Fairino TCP format (degrees in)."""
    rx = math.radians(rx_deg)
    ry = math.radians(ry_deg)
    rz = math.radians(rz_deg)
    Rx = np.array([
        [1, 0, 0],
        [0, math.cos(rx), -math.sin(rx)],
        [0, math.sin(rx), math.cos(rx)],
    ], dtype=np.float64)
    Ry = np.array([
        [math.cos(ry), 0, math.sin(ry)],
        [0, 1, 0],
        [-math.sin(ry), 0, math.cos(ry)],
    ], dtype=np.float64)
    Rz = np.array([
        [math.cos(rz), -math.sin(rz), 0],
        [math.sin(rz), math.cos(rz), 0],
        [0, 0, 1],
    ], dtype=np.float64)
    return Rz @ Ry @ Rx


def tcp_to_matrix(pose: List[float]) -> np.ndarray:
    """[x_mm, y_mm, z_mm, rx_deg, ry_deg, rz_deg] → 4×4 homogeneous transform."""
    x, y, z, rx, ry, rz = pose
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = euler_to_rotmat(rx, ry, rz)
    T[:3, 3] = [x, y, z]
    return T


def generate_diverse_poses(
    home_pose: List[float],
    n_poses: int,
    rx_range_deg: float,
    ry_range_deg: float,
    rz_range_deg: float,
    xy_range_mm: float,
    z_range_mm: float,
    rng_seed: int = 42,
) -> List[List[float]]:
    """
    Sample n_poses absolute poses within specified ranges around home_pose.

    Uses a scrambled Latin-hypercube strategy across all 6 axes so that
    samples are spread evenly — avoids clustering that pure random gives.

    Returns list of [x, y, z, rx, ry, rz] in mm / degrees.
    """
    rng = np.random.default_rng(rng_seed)
    x0, y0, z0, rx0, ry0, rz0 = home_pose

    half_ranges = np.array([xy_range_mm, xy_range_mm, z_range_mm,
                             rx_range_deg, ry_range_deg, rz_range_deg])
    centers = np.array([x0, y0, z0, rx0, ry0, rz0])

    # Latin hypercube: divide [0,1) into n_poses bins, sample one per bin per axis
    lhs = np.zeros((n_poses, 6))
    for col in range(6):
        perm = rng.permutation(n_poses)
        lhs[:, col] = (perm + rng.random(n_poses)) / n_poses

    # Map [0,1) → [-range, +range] around centers
    raw = centers + (lhs * 2.0 - 1.0) * half_ranges
    return [raw[i].tolist() for i in range(n_poses)]


def detect_board_center(
    frame: np.ndarray,
    pattern_size: Tuple[int, int],
) -> Optional[Tuple[float, float]]:
    """Legacy wrapper — returns (cx, cy) only."""
    info = detect_board_info(frame, pattern_size)
    return (info.cx, info.cy) if info is not None else None


def detect_board_info(
    frame: np.ndarray,
    pattern_size: Tuple[int, int],
) -> Optional[BoardInfo]:
    """
    Lightweight chessboard detection returning center, bounding-box dimensions
    and area in pixels — no PnP, no camera params required.  Used in the servo
    loop.  Returns None if the board is not found.
    """
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    found, corners = cv2.findChessboardCorners(
        gray, pattern_size, flags=cv2.CALIB_CB_FAST_CHECK,
    )
    if not found or corners is None:
        found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
    if not found or corners is None:
        return None
    pts = corners.reshape(-1, 2)
    cx = float(pts[:, 0].mean())
    cy = float(pts[:, 1].mean())
    x_min, y_min = pts.min(axis=0)
    x_max, y_max = pts.max(axis=0)
    bbox_w = float(x_max - x_min)
    bbox_h = float(y_max - y_min)
    area = bbox_w * bbox_h
    return BoardInfo(cx=cx, cy=cy, bbox_w=bbox_w, bbox_h=bbox_h, area=area)


def detect_chessboard_pose(
    frame: np.ndarray,
    pattern_size: Tuple[int, int],
    square_size_mm: float,
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], np.ndarray]:
    """
    Detect chessboard inner corners and compute board-to-camera transform.

    pattern_size = (inner_cols, inner_rows)

    Returns:
        R_cam  — 3×3 rotation (board frame → camera frame), or None if not found
        t_cam  — 3×1 translation (mm), or None if not found
        annotated_frame — copy of frame with corners / axes drawn
    """
    annotated = frame.copy()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame.copy()

    found, corners = cv2.findChessboardCorners(gray, pattern_size, None)
    if not found or corners is None:
        return None, None, annotated

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    cv2.drawChessboardCorners(annotated, pattern_size, corners, found)

    cols, rows = pattern_size
    objp = np.zeros((cols * rows, 3), dtype=np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_size_mm

    ok, rvec, tvec = cv2.solvePnP(objp, corners, camera_matrix, dist_coeffs)
    if not ok:
        return None, None, annotated

    cv2.drawFrameAxes(annotated, camera_matrix, dist_coeffs, rvec, tvec, square_size_mm * 2)

    R_cam, _ = cv2.Rodrigues(rvec)
    t_cam = tvec.reshape(3, 1)
    return R_cam, t_cam, annotated


def compute_hand_eye(
    R_robot: List[np.ndarray],
    t_robot: List[np.ndarray],
    R_cam: List[np.ndarray],
    t_cam: List[np.ndarray],
    method: int = cv2.CALIB_HAND_EYE_TSAI,
) -> np.ndarray:
    """
    Run cv2.calibrateHandEye and return the 4×4 camera-to-flange transform.

    Input lists must all have the same length (≥ 4 samples).
    """
    R_c2f, t_c2f = cv2.calibrateHandEye(R_robot, t_robot, R_cam, t_cam, method=method)
    T = np.eye(4, dtype=np.float64)
    T[:3, :3] = R_c2f
    T[:3, 3] = t_c2f.reshape(3)
    return T
