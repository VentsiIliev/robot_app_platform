"""Run Network Settings with an in-memory adapter, without changing host networking."""

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.network_settings.network_settings_factory import NetworkSettingsFactory
from src.applications.network_settings.service.stub_network_settings_service import StubNetworkSettingsService


def run_standalone() -> None:
    app = QApplication(sys.argv)
    widget = NetworkSettingsFactory().build(StubNetworkSettingsService())
    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 850)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
