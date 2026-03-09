import sys

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.applications.height_measuring.height_measuring_factory import HeightMeasuringFactory
from src.applications.height_measuring.service.stub_height_measuring_app_service import StubHeightMeasuringAppService


def run_standalone():
    app    = QApplication(sys.argv)
    widget = HeightMeasuringFactory().build(StubHeightMeasuringAppService())
    window = QMainWindow()
    window.setWindowTitle("Height Measuring — standalone")
    window.setCentralWidget(widget)
    window.resize(1280, 1024)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()

