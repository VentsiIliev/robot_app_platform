import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import cv2
import numpy as np
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMainWindow, QToolBar

from src.engine.core.messaging_service import MessagingService
from src.robot_systems.paint.applications.dashboard.paint_dashboard_factory import (
    PaintDashboardFactory,
)
from src.robot_systems.paint.applications.dashboard.service.stub_paint_dashboard_service import (
    StubPaintDashboardService,
)
from src.shared_contracts.events.process_events import ProcessState, ProcessStateEvent, ProcessTopics
from src.shared_contracts.events.robot_events import RobotTopics
from src.shared_contracts.events.vision_events import VisionTopics

_FRAME_WIDTH = 800
_FRAME_HEIGHT = 450


def _make_demo_frame(tick: int) -> np.ndarray:
    frame = np.zeros((_FRAME_HEIGHT, _FRAME_WIDTH, 3), dtype=np.uint8)
    cv2.rectangle(frame, (0, 0), (_FRAME_WIDTH - 1, _FRAME_HEIGHT - 1), (40, 40, 48), -1)
    x = 60 + (tick * 8) % (_FRAME_WIDTH - 120)
    cv2.circle(frame, (x, _FRAME_HEIGHT // 2), 22, (90, 180, 90), -1)
    cv2.putText(
        frame,
        "SIMULATED CAMERA FEED",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (200, 200, 220),
        2,
        cv2.LINE_AA,
    )
    cv2.putText(
        frame,
        f"tick {tick}",
        (20, _FRAME_HEIGHT - 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (140, 140, 160),
        1,
        cv2.LINE_AA,
    )
    return frame


class _DemoHarness(QMainWindow):
    """Adds broker-event injection buttons so the dashboard can be tested live."""

    def __init__(self, widget, messaging: MessagingService) -> None:
        super().__init__()
        self._messaging = messaging
        self._camera_running = False
        self._tick = 0

        self.setCentralWidget(widget)
        self.resize(1280, 900)
        self.setWindowTitle("Paint Dashboard — Standalone")

        toolbar = QToolBar("Demo Events")
        self.addToolBar(toolbar)

        camera_btn = toolbar.addAction("Camera feed")
        camera_btn.triggered.connect(self._toggle_camera)
        toolbar.addAction("Warning", self._send_warning)
        toolbar.addAction("No workpiece", self._send_no_workpiece)
        toolbar.addAction("Flood messages", self._send_flood)
        toolbar.addAction("Robot disconnected", self._send_robot_disconnected)

        self._camera_timer = QTimer(self)
        self._camera_timer.setInterval(100)
        self._camera_timer.timeout.connect(self._publish_frame)

    def _toggle_camera(self) -> None:
        self._camera_running = not self._camera_running
        if self._camera_running:
            self._camera_timer.start()
        else:
            self._camera_timer.stop()

    def _publish_frame(self) -> None:
        self._tick += 1
        self._messaging.publish(
            VisionTopics.LATEST_IMAGE,
            {"image": _make_demo_frame(self._tick)},
        )

    def _publish_process_event(self, state: ProcessState, message: str) -> None:
        self._messaging.publish(
            ProcessTopics.ACTIVE,
            ProcessStateEvent(process_id="paint", state=state, previous=ProcessState.IDLE, message=message),
        )

    def _send_warning(self) -> None:
        self._publish_process_event(
            ProcessState.ERROR,
            "Paint supply tank pressure is below the minimum threshold, please refill soon",
        )

    def _send_no_workpiece(self) -> None:
        self._publish_process_event(
            ProcessState.ERROR,
            "No workpiece was found in the camera view",
        )

    def _send_flood(self) -> None:
        for index in range(30):
            self._publish_process_event(
                ProcessState.ERROR,
                f"Diagnostic message {index + 1}: paint supply tank pressure below minimum threshold "
                "and the system needs attention right now",
            )

    def _send_robot_disconnected(self) -> None:
        self._messaging.publish(RobotTopics.STATE, {"state": "disconnected", "extra": {}})


def run_standalone() -> None:
    app = QApplication(sys.argv)

    messaging = MessagingService()
    service = StubPaintDashboardService()
    widget = PaintDashboardFactory().build(service, messaging=messaging)

    harness = _DemoHarness(widget, messaging)
    harness.show()

    if "--smoke" in sys.argv:
        QTimer.singleShot(1500, app.quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
