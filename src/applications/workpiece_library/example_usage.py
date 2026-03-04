#!/usr/bin/env python3
import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s")

from PyQt6.QtWidgets import QApplication, QMainWindow
from src.applications.workpiece_library.workpiece_library_factory import WorkpieceLibraryFactory
from src.applications.workpiece_library.service.stub_workpiece_library_service import StubWorkpieceLibraryService


def run_standalone():
    app    = QApplication(sys.argv)
    widget = WorkpieceLibraryFactory().build(StubWorkpieceLibraryService())
    window = QMainWindow()
    window.setWindowTitle("Workpiece Library — Standalone")
    window.setCentralWidget(widget)
    window.resize(1280, 1024)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()