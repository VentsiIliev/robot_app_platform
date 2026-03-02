import sys
from PyQt6.QtWidgets import QApplication, QMainWindow
from src.applications.camera_settings import StubCameraSettingsService
from src.applications.camera_settings.camera_settings_factory import CameraSettingsFactory
from src.engine.core.messaging_service import MessagingService


def run_standalone():
    app        = QApplication(sys.argv)
    service    = StubCameraSettingsService()
    messaging  = MessagingService()
    widget     = CameraSettingsFactory().build(service, messaging)
    window     = QMainWindow()
    window.setWindowTitle("Camera Settings")
    window.setCentralWidget(widget)
    window.resize(1280, 1024)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()