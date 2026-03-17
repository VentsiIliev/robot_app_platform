import sys
import pathlib

if __package__ in {None, ""}:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[5]))


def run_standalone():
    from PyQt6.QtWidgets import QApplication, QMainWindow

    from src.robot_systems.glue.applications.glue_process_driver.glue_process_driver_factory import (
        GlueProcessDriverFactory,
    )
    from src.robot_systems.glue.applications.glue_process_driver.service.stub_glue_process_driver_service import (
        StubGlueProcessDriverService,
    )
    from src.engine.core.message_broker import MessageBroker

    app = QApplication(sys.argv)
    widget = GlueProcessDriverFactory(MessageBroker()).build(StubGlueProcessDriverService())
    window = QMainWindow()
    window.setCentralWidget(widget)
    window.resize(1400, 900)
    window.setWindowTitle("Glue Process Driver")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
