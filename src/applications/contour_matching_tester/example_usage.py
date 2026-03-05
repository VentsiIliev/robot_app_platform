def run_standalone() -> None:
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow
    from src.applications.contour_matching_tester.contour_matching_tester_factory import ContourMatchingTesterFactory
    from src.applications.contour_matching_tester.service.stub_contour_matching_tester_service import StubContourMatchingTesterService

    app    = QApplication(sys.argv)
    widget = ContourMatchingTesterFactory().build(StubContourMatchingTesterService(), messaging=None)

    window = QMainWindow()
    window.setWindowTitle("Contour Matching Tester")
    window.setCentralWidget(widget)
    window.resize(1280, 800)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()

