"""
Standalone runner for the IntrinsicCaptureApplication.

Uses mock robot and vision services so no hardware is required.
Run with:
    python src/applications/intrinsic_calibration_capture/example_usage.py
"""
from __future__ import annotations

import sys
import os
import numpy as np

# ── Mock services ─────────────────────────────────────────────────────────────

class MockRobotConfig:
    robot_tool = 0
    robot_user = 0

    class global_motion_settings:
        global_velocity = 30
        global_acceleration = 10


class MockRobotService:
    """Returns a fixed pose; all moves succeed instantly."""

    def __init__(self):
        self._pose = [300.0, 0.0, 400.0, 0.0, 0.0, 0.0]

    def get_current_position(self):
        return list(self._pose)

    def move_ptp(self, position, tool=0, user=0, velocity=30, acceleration=10, wait_to_reach=True):
        self._pose = list(position)
        return True


class MockVisionService:
    """
    Returns a synthetic chessboard image so detection always succeeds.
    Chessboard: 9 cols × 6 rows inner corners, 60px squares, centred in 1280×720.
    """

    _COLS = 9
    _ROWS = 6
    _SQUARE = 60

    def __init__(self):
        self._frame = self._make_board()

    def _make_board(self) -> np.ndarray:
        import cv2
        w, h = 1280, 720
        img = np.ones((h, w, 3), dtype=np.uint8) * 200  # light grey background

        cols, rows = self._COLS + 1, self._ROWS + 1   # squares = inner corners + 1
        sq = self._SQUARE
        board_w = cols * sq
        board_h = rows * sq
        ox = (w - board_w) // 2
        oy = (h - board_h) // 2

        for r in range(rows):
            for c in range(cols):
                color = 0 if (r + c) % 2 == 0 else 255
                x0, y0 = ox + c * sq, oy + r * sq
                img[y0:y0 + sq, x0:x0 + sq] = color

        return img

    def get_latest_frame(self) -> np.ndarray:
        return self._frame.copy()

    def get_chessboard_width(self) -> int:
        return self._COLS

    def get_chessboard_height(self) -> int:
        return self._ROWS

    def get_camera_width(self) -> int:
        return 1280

    def get_camera_height(self) -> int:
        return 720


# ── App bootstrap ─────────────────────────────────────────────────────────────

def main():
    # Must import Qt before creating widgets
    from PyQt6.QtWidgets import QApplication
    app = QApplication(sys.argv)

    from src.applications.intrinsic_calibration_capture.service.intrinsic_capture_service import (
        IntrinsicCaptureService,
    )
    from src.applications.intrinsic_calibration_capture.intrinsic_capture_factory import (
        IntrinsicCaptureFactory,
    )

    robot = MockRobotService()
    vision = MockVisionService()
    config = MockRobotConfig()

    service = IntrinsicCaptureService(
        robot_service=robot,
        vision_service=vision,
        robot_config=config,
        messaging=None,
    )

    widget = IntrinsicCaptureFactory().build(service, messaging=None)
    widget.setWindowTitle("Intrinsic Calibration Capture — standalone test")
    widget.resize(700, 800)
    widget.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    # Ensure project root is on the path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    main()
