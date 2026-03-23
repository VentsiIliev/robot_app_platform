"""
CameraView demo — no robot, no broker, no real camera.

Simulates a live feed via a QTimer that generates simple gradient frames.
Pre-registers two areas and activates one for interactive editing.

Run with:
    python pl_gui/utils/utils_widgets/camera_view_demo.y_pixels
"""
import sys
import random

import numpy as np

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget

# Allow running from repo root
sys.path.insert(0, ".")
from pl_gui.utils.utils_widgets.camera_view import CameraView  # noqa: E402


def _make_frame(width: int = 640, height: int = 480, tick: int = 0) -> QPixmap:
    """Generate a simple animated gradient frame as QPixmap (no cv2)."""
    # Gradient + some noise to simulate a live camera
    x = np.linspace(0, 1, width, dtype=np.float32)
    y = np.linspace(0, 1, height, dtype=np.float32)
    xx, yy = np.meshgrid(x, y)

    t = tick * 0.03
    r = np.clip((np.sin(xx * 4 + t) * 0.5 + 0.5) * 200, 0, 255).astype(np.uint8)
    g = np.clip((np.sin(yy * 3 - t) * 0.5 + 0.5) * 180, 0, 255).astype(np.uint8)
    b = np.clip((np.cos((xx + yy) * 2 + t) * 0.5 + 0.5) * 220, 0, 255).astype(np.uint8)

    noise = np.random.randint(-12, 12, (height, width), dtype=np.int16)
    r = np.clip(r.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    rgb = np.stack([r, g, b], axis=2)
    h, w, ch = rgb.shape
    img = QImage(bytes(rgb.tobytes()), w, h, ch * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(img)


class _DemoWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CameraView Demo")
        self.resize(900, 620)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Status label at the top
        self._status = QLabel("Signals will appear here")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            "background: #1A1A2A; color: #CCC; font-size: 9pt; padding: 4px;"
        )
        layout.addWidget(self._status)

        # CameraView
        self._view = CameraView()
        layout.addWidget(self._view, stretch=1)

        # Register two areas
        self._view.add_area("pickup_area")           # green (from palette)
        self._view.add_area("brightness_area")       # amber (from palette)

        # Pre-populate corners
        self._view.set_area_corners("pickup_area", [
            (0.05, 0.05), (0.45, 0.05), (0.45, 0.95), (0.05, 0.95),
        ])
        self._view.set_area_corners("brightness_area", [
            (0.55, 0.25), (0.95, 0.25), (0.95, 0.75), (0.55, 0.75),
        ])

        # Activate brightness_area for editing
        self._view.set_active_area("brightness_area")

        # Connect signals → status label
        self._view.corner_updated.connect(self._on_corner_updated)
        self._view.empty_clicked.connect(self._on_empty_clicked)

        # Animated feed
        self._tick = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._push_frame)
        self._timer.start(33)   # ~30 fps

    def _push_frame(self) -> None:
        self._view.set_frame(_make_frame(tick=self._tick))
        self._tick += 1

    def _on_corner_updated(self, area: str, idx: int, xn: float, yn: float) -> None:
        msg = f"corner_updated  area={area!r}  idx={idx}  x={xn:.3f}  y={yn:.3f}"
        print(msg)
        self._status.setText(msg)

    def _on_empty_clicked(self, area: str, xn: float, yn: float) -> None:
        msg = f"empty_clicked   area={area!r}  x={xn:.3f}  y={yn:.3f}"
        print(msg)
        self._status.setText(msg)


def main() -> None:
    app = QApplication(sys.argv)
    win = _DemoWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
