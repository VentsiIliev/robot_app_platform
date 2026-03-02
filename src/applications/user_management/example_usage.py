import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

from PyQt6.QtWidgets import QApplication, QMainWindow
from src.applications.user_management.service.stub_user_management_service import StubUserManagementService
from src.applications.user_management.user_management_factory import UserManagementFactory


def run_standalone():
    app    = QApplication(sys.argv)
    widget = UserManagementFactory().build(StubUserManagementService())
    window = QMainWindow()
    window.setWindowTitle("User Management — Standalone")
    window.setCentralWidget(widget)
    window.resize(1100, 700)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()

