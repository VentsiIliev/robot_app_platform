"""
Standalone runner for the Login application.

Demonstrates two scenarios:
  1. Normal login   — stub always accepts any numeric ID + password.
  2. First-run      — is_first_run()=True, so the first-admin creation form is shown.
  3. QR auto-login  — try_qr_login() returns credentials after a short delay,
                      simulating automatic QR code detection.

Run from the project root:
    python src/applications/login/example_usage.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

from typing import Optional, Tuple

from PyQt6.QtWidgets import QApplication, QMessageBox

from src.applications.login.login_factory import LoginFactory
from src.applications.login.stub_login_application_service import StubLoginApplicationService
from src.engine.auth.i_authenticated_user import IAuthenticatedUser


# ── Stub variants ─────────────────────────────────────────────────────────────

class _FirstRunStub(StubLoginApplicationService):
    """Pretends no users exist — triggers the first-admin creation page."""
    def is_first_run(self) -> bool:
        return True


class _QrAutoStub(StubLoginApplicationService):
    """Simulates a QR code being detected on the first poll tick."""
    _scanned = False

    def try_qr_login(self) -> Optional[Tuple[str, str]]:
        if not self._scanned:
            self._scanned = True
            return "1", "stubpassword"
        return None

    def move_to_login_pos(self) -> None:
        print("[Stub] Robot moving to login position…")


# ── Runner helper ─────────────────────────────────────────────────────────────

def _run(service, title: str) -> None:
    dialog = LoginFactory.build(service)
    dialog.setWindowTitle(title)
    accepted = dialog.exec() == dialog.DialogCode.Accepted
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
    app = QApplication(sys.argv)

    # 1. Normal login (password tab)
    _run(StubLoginApplicationService(), "Login — Normal flow")

    # 2. First-run: first-admin creation page
    _run(_FirstRunStub(), "Login — First-run setup")

    # 3. QR auto-login: switch to QR tab; stub returns credentials on first poll
    _run(_QrAutoStub(), "Login — QR auto-login (switch to QR tab to trigger)")

    sys.exit(0)


if __name__ == "__main__":
    run_standalone()
