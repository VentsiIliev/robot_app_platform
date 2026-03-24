import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.work_area_settings import (
    StubWorkAreaSettingsService,
    WorkAreaSettingsFactory,
)
from src.engine.core.messaging_service import MessagingService
from src.shared_contracts.declarations import WorkAreaDefinition


def run_standalone():
    app = QApplication(sys.argv)
    service = StubWorkAreaSettingsService()
    messaging = MessagingService()
    widget = WorkAreaSettingsFactory(
        work_area_definitions=[
            WorkAreaDefinition(id="default", label="Default", color="#50DC64", supports_brightness_roi=True),
        ]
    ).build(service, messaging)
    window = QMainWindow()
    window.setWindowTitle("Work Area Settings")
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
