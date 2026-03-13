import sys
from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.device_control.device_control_factory import DeviceControlFactory
from src.applications.device_control.service.stub_device_control_service import StubDeviceControlService


def run_standalone():
    app = QApplication(sys.argv)
    widget = DeviceControlFactory().build(StubDeviceControlService())
    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(800, 600)
    window.setWindowTitle("DeviceControl — standalone")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()

