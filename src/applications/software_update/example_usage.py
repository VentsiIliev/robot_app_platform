import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from PyQt6.QtWidgets import QApplication, QMainWindow
from src.applications.software_update import SoftwareUpdateApplication
from src.applications.software_update.software_update_factory import SoftwareUpdateFactory
from src.applications.software_update.service.stub_software_update_service import StubSoftwareUpdateService


def run_standalone():
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setCentralWidget(SoftwareUpdateFactory().build(StubSoftwareUpdateService()))
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
