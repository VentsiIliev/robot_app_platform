import sys


def run_standalone() -> None:
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.pick_target.pick_target_factory import PickTargetFactory
    from src.applications.pick_target.service.stub_pick_target_service import StubPickTargetService

    app    = QApplication(sys.argv)
    widget = PickTargetFactory().build(StubPickTargetService())
    window = QMainWindow()
    window.setWindowTitle("Pick Target")
    window.setCentralWidget(widget)
    window.resize(1024, 680)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
