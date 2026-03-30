import sys
import logging
import threading
import time
import numpy as np

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.calibration_v2.calibration_factory import CalibrationFactory
from src.applications.calibration.service.stub_calibration_service import StubCalibrationService
from src.engine.core.messaging_service import MessagingService
from src.shared_contracts.events.vision_events import VisionTopics


def _publish_fake_frames(messaging: MessagingService, stop: threading.Event) -> None:
    frame_count = 0
    while not stop.is_set():
        # 640×480 BGR image — cycling hue so you can see it's live
        hue = int((frame_count * 2) % 180)
        hsv = np.full((480, 640, 3), (hue, 180, 200), dtype=np.uint8)
        import cv2
        bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

        # draw frame counter so motion is obvious
        cv2.putText(bgr, f"frame {frame_count}", (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)

        messaging.publish(VisionTopics.LATEST_IMAGE, {"image": bgr})
        frame_count += 1
        stop.wait(0.033)   # ~30 fps


def run_standalone():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    )

    app       = QApplication(sys.argv)
    messaging = MessagingService()

    stop_event = threading.Event()
    thread = threading.Thread(
        target=_publish_fake_frames,
        args=(messaging, stop_event),
        daemon=True,
        name="fake-camera",
    )
    thread.start()

    widget = CalibrationFactory().build(StubCalibrationService(), messaging=messaging)
    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 1024)
    window.setWindowTitle("Calibration — Standalone")
    window.destroyed.connect(stop_event.set)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
