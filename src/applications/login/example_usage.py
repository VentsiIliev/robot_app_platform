"""
Standalone runner for the Login application.

Demonstrates three scenarios:
  1. Normal login   — stub always accepts any numeric ID + password.
  2. First-run      — is_first_run()=True → first-admin creation form.
  3. QR auto-login  — try_qr_login() returns credentials after 4 s;
                      fake camera frames are published so the live feed works.

Run from the project root:
    python src/applications/login/example_usage.y_pixels [normal|first_run|qr]
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

import numpy as np
from typing import Optional, Tuple

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.applications.login.login_factory import LoginFactory
from src.applications.login.stub_login_application_service import StubLoginApplicationService
from src.engine.auth.i_authenticated_user import IAuthenticatedUser
from src.engine.core.message_broker import MessageBroker
from src.shared_contracts.events.vision_events import VisionTopics


# ── Stub variants ─────────────────────────────────────────────────────────────

class _FirstRunStub(StubLoginApplicationService):
    def is_first_run(self) -> bool:
        return True


class _QrAutoStub(StubLoginApplicationService):
    _scanned = False

    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        if self._scanned:
            return None
        self._scanned = True
        return "1", "stubpassword"

    def move_to_login_pos(self) -> None:
        print("[Stub] Robot moving to login position…")


# ── Fake camera feed publisher ────────────────────────────────────────────────

class _FakeCameraPublisher:
    """Publishes synthetic BGR frames at ~15 fps so the CameraView has something to show."""

    _HUE_STEP = 2

    def __init__(self):
        self._broker = MessageBroker()
        self._hue    = 0
        self._timer  = QTimer()
        self._timer.setInterval(66)   # ~15 fps
        self._timer.timeout.connect(self._publish)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _publish(self) -> None:
        import cv2
        # Solid colour that cycles through hues — cheap and clearly "live"
        hsv   = np.full((360, 640, 3), (self._hue, 200, 200), dtype=np.uint8)
        frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        self._hue = (self._hue + self._HUE_STEP) % 180

        # Overlay label so it's obvious this is a stub frame
        cv2.putText(
            frame, "[ Stub camera feed ]",
            (160, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2,
        )
        self._broker.publish(VisionTopics.LATEST_IMAGE, {"image": frame})


# ── Runner helper ─────────────────────────────────────────────────────────────

def _run(service, title: str, with_camera: bool = False) -> None:
    cam = _FakeCameraPublisher() if with_camera else None

    # IMessagingService — use the real singleton for the standalone demo
    from src.engine.core.messaging_service import MessagingService
    messaging = MessagingService()

    dialog = LoginFactory.build(service, messaging=messaging)
    dialog.setWindowTitle(title)

    if cam:
        cam.start()

    accepted = dialog.exec() == dialog.DialogCode.Accepted

    if cam:
        cam.stop()

    if accepted:
        user: IAuthenticatedUser = dialog.result_user()
        QMessageBox.information(
            None, "Logged in",
            f"User ID : {user.user_id}\nRole     : {user.role}",
        )
    else:
        QMessageBox.warning(None, "Closed", "Login dialog was closed without logging in.")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_standalone() -> None:
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "normal"
    app  = QApplication(sys.argv)

    if mode == "first_run":
        _run(_FirstRunStub(), "Login — First-run setup")
    elif mode == "qr":
        _run(_QrAutoStub(), "Login — QR auto-login (switch to QR tab)", with_camera=True)
    else:
        _run(StubLoginApplicationService(), "Login — Normal flow", with_camera=True)

    sys.exit(0)


if __name__ == "__main__":
    run_standalone()
