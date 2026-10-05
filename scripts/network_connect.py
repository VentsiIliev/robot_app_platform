"""Standalone launcher for the shared Network Settings application.

Run from the repository root with ``python scripts/network_connect.py``.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMainWindow

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.applications.network_settings.network_settings_factory import NetworkSettingsFactory
from src.applications.network_settings.service.network_settings_service import NetworkSettingsService


def main() -> None:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("Network Settings")
    window.setCentralWidget(NetworkSettingsFactory().build(NetworkSettingsService()))
    window.resize(1280, 850)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
