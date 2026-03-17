"""
Standalone runner for the Login application.

Runs two demo scenarios back-to-back:
  1. Normal login  — StubLoginApplicationService always authenticates.
  2. First-run     — service reports is_first_run()=True, so the first-admin
                     creation page is shown instead.

Run from the project root:
    python src/applications/login/example_usage.py
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

from PyQt6.QtWidgets import QApplication, QLabel, QMessageBox

from src.applications.login.login_factory import LoginFactory
from src.applications.login.stub_login_application_service import StubLoginApplicationService


# ── Scenario helpers ─────────────────────────────────────────────────────────

class _FirstRunStub(StubLoginApplicationService):
    """Stub that pretends no users exist yet (first-run flow)."""
    def is_first_run(self) -> bool:
        return True


def _run_scenario(service, title: str) -> None:
    dialog = LoginFactory.build(service)
    dialog.setWindowTitle(title)
    result = dialog.exec()
    if result == dialog.DialogCode.Accepted:
        user = dialog.result_user()
        QMessageBox.information(
            None,
            "Logged in",
            f"User ID : {user.user_id}\nRole     : {user.role}",
        )
    else:
        QMessageBox.warning(None, "Cancelled", "Login dialog was closed.")


# ── Entry point ──────────────────────────────────────────────────────────────

def run_standalone() -> None:
    app = QApplication(sys.argv)

    # Scenario 1: normal login page
    _run_scenario(StubLoginApplicationService(), "Login — Normal flow (stub)")

    # Scenario 2: first-run admin creation page
    _run_scenario(_FirstRunStub(), "Login — First-run flow (stub)")

    sys.exit(0)


if __name__ == "__main__":
    run_standalone()
