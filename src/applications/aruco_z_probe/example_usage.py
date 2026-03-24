import sys


def run_standalone() -> None:
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.aruco_z_probe.aruco_z_probe_factory import ArucoZProbeFactory
    from src.applications.aruco_z_probe.service.stub_aruco_z_probe_service import StubArucoZProbeService

    app    = QApplication(sys.argv)
    widget = ArucoZProbeFactory().build(StubArucoZProbeService())
    window = QMainWindow()
    window.setWindowTitle("ArUco Z Probe")
    window.setCentralWidget(widget)
    window.resize(1100, 680)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
