"""
Standalone runner for the legacy LoginWindow.

Run from the project root:
    python login/example_usage.py

Three demo modes (passed as CLI argument):
    python login/example_usage.py normal    — username/password login (default)
    python login/example_usage.py qr        — starts on QR tab; auto-login after 4 s
    python login/example_usage.py setup     — shows setup-steps page first

Credentials accepted by the mock:
    Any numeric ID + any non-empty password → success
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

from typing import Any, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

from login._compat import Constants, auth_endpoints, camera_endpoints


# ── Mock response ─────────────────────────────────────────────────────────────

class _Response:
    def __init__(self, status: str, data: dict):
        self.status = status
        self.data   = data


# ── Mock controller ───────────────────────────────────────────────────────────

class MockController:
    """
    Simulates the backend controller the legacy LoginWindow expects.

    - handleLogin(id, pw) → "1" success / "0" wrong pw / "-1" not found
    - handleLoginPos()    → robot moves to login position (no-op)
    - handle(endpoint)    → camera / auth endpoint dispatcher
    """

    def __init__(self, qr_success_after_ms: Optional[int] = None):
        self._qr_success_after_ms = qr_success_after_ms
        self._qr_ready = False
        if qr_success_after_ms is not None:
            QTimer.singleShot(qr_success_after_ms, self._arm_qr)

    def _arm_qr(self) -> None:
        print("[MockController] QR payload armed — next poll will succeed")
        self._qr_ready = True

    def handleLogin(self, username: str, password: str) -> str:
        print(f"[MockController] handleLogin({username!r}, ***)")
        if not username or not password:
            return "-1"
        if not username.isdigit():
            return "-1"
        # Accept any valid-looking credentials for demo
        return "1"

    def handleLoginPos(self) -> None:
        print("[MockController] Robot moving to login position…")

    def handle(self, endpoint: Any) -> Any:
        ep = str(endpoint)
        print(f"[MockController] handle({ep!r})")

        if ep == str(auth_endpoints.QR_LOGIN):
            if self._qr_ready:
                self._qr_ready = False   # one-shot
                return _Response(
                    status=Constants.RESPONSE_STATUS_SUCCESS,
                    data={"id": "42", "password": "qrsecret"},
                )
            return _Response(status="no_qr", data={})

        # camera and all other endpoints — no-op
        return None


# ── Entry point ───────────────────────────────────────────────────────────────

def run_standalone() -> None:
    # Determine demo mode from CLI
    mode = sys.argv[1].lower() if len(sys.argv) > 1 else "normal"

    app = QApplication(sys.argv)

    if mode == "qr":
        # QR auto-login: payload arrives after 4 seconds
        controller = MockController(qr_success_after_ms=4000)
        config_override = {"DEFAULT_LOGIN": "QR"}
    else:
        controller = MockController()
        config_override = {}

    def on_login_success():
        print("=== Login successful — main application would start here ===")
        QMessageBox.information(None, "Success", "Login successful!\nMain application would open now.")

    # Import here so sys.path is already patched
    from login.LoginWindow import LoginWindow

    window = LoginWindow(
        controller=controller,
        onLogEventCallback=on_login_success,
    )

    # Override settings for demo modes
    window.ui_settings.update(config_override)

    if mode == "setup":
        # Show the setup-steps page instead of the tabs
        window.right_stack.setCurrentWidget(window.step_widget)
    else:
        # Show tabs directly (skip setup steps)
        window.right_stack.setCurrentWidget(window.tabs_widget)
        if mode == "qr":
            window.tabs.setCurrentIndex(0)   # start on login tab; user switches to QR

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
