from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.ethercat_diagnostics.ethercat_diagnostics_factory import (
    EthercatDiagnosticsFactory,
)
from src.applications.ethercat_diagnostics.service.stub_ethercat_diagnostics_service import (
    StubEthercatDiagnosticsService,
)


def run_standalone() -> None:
    app = QApplication(sys.argv)
    widget = EthercatDiagnosticsFactory().build(StubEthercatDiagnosticsService())
    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
