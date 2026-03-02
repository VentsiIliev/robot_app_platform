#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../../')))

import logging
from PyQt6.QtWidgets import QApplication, QMainWindow

from robot_systems.glue.applications.workpiece_editor.workpiece_editor_factory import WorkpieceEditorFactory
from robot_systems.glue.applications.workpiece_editor.service import StubWorkpieceEditorService
from src.engine.core.messaging_service import MessagingService


def run_standalone():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)-8s] %(name)s — %(message)s",
    )

    app       = QApplication(sys.argv)
    messaging = MessagingService()
    service   = StubWorkpieceEditorService()
    widget    = WorkpieceEditorFactory(messaging).build(service)

    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1440, 900)
    window.setWindowTitle("Workpiece Editor — Standalone")
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()