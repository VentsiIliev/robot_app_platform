import sys


def run_standalone() -> None:
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.pick_and_place_visualizer.pick_and_place_visualizer_factory import (
        PickAndPlaceVisualizerFactory,
    )
    from src.applications.pick_and_place_visualizer.service.stub_pick_and_place_visualizer_service import (
        StubPickAndPlaceVisualizerService,
    )

    app    = QApplication(sys.argv)
    widget = PickAndPlaceVisualizerFactory().build(StubPickAndPlaceVisualizerService())
    window = QMainWindow()
    window.setWindowTitle("Pick & Place Visualizer")
    window.setCentralWidget(widget)
    window.resize(1280, 860)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()