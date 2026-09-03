import sys


def run_standalone() -> None:
    from PyQt6.QtWidgets import QApplication, QMainWindow

    from src.applications.shaft_alignment.service.paint_vision_shaft_alignment_service import (
        PaintVisionShaftAlignmentService,
    )
    from src.applications.shaft_alignment.shaft_alignment_factory import ShaftAlignmentFactory

    app = QApplication(sys.argv)
    service = PaintVisionShaftAlignmentService()
    widget = ShaftAlignmentFactory().build(service)
    window = QMainWindow()
    window.setWindowTitle("Shaft Alignment")
    window.setCentralWidget(widget)
    window.resize(1280, 820)
    window.show()
    service.start()
    try:
        exit_code = app.exec()
    finally:
        service.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    run_standalone()
