#!/usr/bin/env python3
"""
Standalone runner for the Hand-Eye Calibration application.

Uses mock services so no hardware is required:
  - MockSnapshotService   — returns a synthetic chessboard frame + varied robot pose
  - MockVisionService     — provides a placeholder camera matrix and output path
  - MockRobotService      — accepts move_ptp commands instantly
  - MockRobotConfig       — provides tool/user numbers

Run:
    python src/applications/hand_eye_calibration/example_usage.py
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import threading
import time
from typing import List, Optional

import cv2
import numpy as np

# Ensure project root is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from src.engine.vision.i_capture_snapshot_service import ICaptureSnapshotService, VisionCaptureSnapshot


# ── Mock services ─────────────────────────────────────────────────────────────

_BOARD_PATTERN = (9, 6)  # inner corners for synthetic board
_SQUARE_MM = 25.0
_SQUARE_PX = 40

# Build 3-D object points so we can project onto a synthetic image
_objp = np.zeros((_BOARD_PATTERN[0] * _BOARD_PATTERN[1], 3), np.float32)
_objp[:, :2] = np.mgrid[0:_BOARD_PATTERN[0], 0:_BOARD_PATTERN[1]].T.reshape(-1, 2) * _SQUARE_MM

# Synthetic camera matrix for a 640×480 sensor
_K = np.array([[600.0, 0.0, 320.0],
               [0.0, 600.0, 240.0],
               [0.0, 0.0, 1.0]], dtype=np.float64)
_DIST = np.zeros((1, 5), dtype=np.float64)

_FRAME_LOCK = threading.Lock()
_latest_frame: Optional[np.ndarray] = None


def _make_synthetic_board_frame(rvec, tvec):
    """Render a synthetic chessboard visible in the camera with given pose."""
    h, w = 480, 640
    img = np.ones((h, w, 3), dtype=np.uint8) * 180

    # Project object points to image
    pts, _ = cv2.projectPoints(_objp, rvec, tvec, _K, _DIST)
    pts = pts.reshape(-1, 2)

    # Check all points are in frame
    if not (np.all(pts[:, 0] > 5) and np.all(pts[:, 0] < w - 5) and
            np.all(pts[:, 1] > 5) and np.all(pts[:, 1] < h - 5)):
        return img  # board out of frame

    # Draw chessboard squares
    cols, rows = _BOARD_PATTERN
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                cv2.rectangle(
                    img,
                    (int(c * _SQUARE_PX + 20), int(r * _SQUARE_PX + 20)),
                    (int((c + 1) * _SQUARE_PX + 20), int((r + 1) * _SQUARE_PX + 20)),
                    (0, 0, 0), -1,
                )
    return img


class MockSnapshotService(ICaptureSnapshotService):
    """Returns a synthetic chessboard frame and a varied robot pose."""

    _pose_index = 0

    def capture_snapshot(self, source: str = "") -> VisionCaptureSnapshot:
        # Vary pose between calls
        idx = MockSnapshotService._pose_index
        MockSnapshotService._pose_index += 1

        rx = math.sin(idx * 0.4) * 20.0
        ry = math.cos(idx * 0.3) * 20.0
        rz = math.sin(idx * 0.2) * 10.0
        pose = [100.0 + idx * 5.0, 200.0 - idx * 3.0, 500.0, rx, ry, rz]

        # Build a matching rvec/tvec so the board is in frame
        rvec = np.array([math.radians(rx), math.radians(ry), math.radians(rz)], dtype=np.float64)
        tvec = np.array([0.0, 0.0, 350.0], dtype=np.float64)
        frame = _make_synthetic_board_frame(rvec, tvec)

        global _latest_frame
        with _FRAME_LOCK:
            _latest_frame = frame

        return VisionCaptureSnapshot(frame=frame, robot_pose=pose)


class MockVisionService:
    cameraMatrix = _K
    cameraDist = _DIST
    camera_to_robot_matrix_path = os.path.join(tempfile.gettempdir(), "mock_hand_eye_result.npy")

    def get_latest_frame(self) -> Optional[np.ndarray]:
        with _FRAME_LOCK:
            return _latest_frame


class MockRobotService:
    def get_current_position(self) -> List[float]:
        return [0.0, 300.0, 500.0, 175.0, 0.0, 0.0]

    def move_ptp(self, position, tool, user, velocity, acceleration, wait_to_reach=True) -> bool:
        time.sleep(0.05)  # simulate fast move
        return True


class MockRobotConfig:
    robot_tool = 1
    robot_user = 1


# ── Run the application ───────────────────────────────────────────────────────

def main():
    from PyQt6.QtWidgets import QApplication, QScrollArea

    from src.applications.hand_eye_calibration.hand_eye_calibration_factory import HandEyeCalibrationFactory
    from src.applications.hand_eye_calibration.service.hand_eye_service import HandEyeCalibrationService
    from src.applications.hand_eye_calibration.service.i_hand_eye_service import HandEyeConfig

    app = QApplication(sys.argv)

    snapshot_svc = MockSnapshotService()
    robot_svc = MockRobotService()
    vision_svc = MockVisionService()
    robot_cfg = MockRobotConfig()

    service = HandEyeCalibrationService(
        snapshot_service=snapshot_svc,
        robot_service=robot_svc,
        vision_service=vision_svc,
        robot_config=robot_cfg,
    )
    # Use a small board so the mock renders correctly
    service.save_config(HandEyeConfig(
        chessboard_width=_BOARD_PATTERN[0],
        chessboard_height=_BOARD_PATTERN[1],
        square_size_mm=_SQUARE_MM,
        n_poses=12,
        rx_range_deg=20.0,
        ry_range_deg=20.0,
        rz_range_deg=10.0,
        xy_range_mm=30.0,
        z_range_mm=50.0,
        stabilization_delay_s=0.0,
    ))

    widget = HandEyeCalibrationFactory().build(service)

    scroll = QScrollArea()
    scroll.setWidget(widget)
    scroll.setWidgetResizable(True)
    scroll.setWindowTitle("Hand-Eye Calibration — Example")
    scroll.resize(700, 900)
    scroll.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
