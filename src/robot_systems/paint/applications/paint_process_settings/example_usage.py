import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[5]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from PyQt6.QtWidgets import QApplication, QMainWindow

from src.robot_systems.paint.applications.paint_process_settings.paint_process_settings_factory import (
    PaintProcessSettingsFactory,
)
from src.robot_systems.paint.applications.paint_process_settings.service.stub_paint_process_settings_service import (
    StubPaintProcessSettingsService,
)


def run_standalone() -> None:
    app = QApplication(sys.argv)
    widget = PaintProcessSettingsFactory().build(StubPaintProcessSettingsService())
    window = QMainWindow()
    window.setWindowTitle("Paint Process Settings")
    window.setCentralWidget(widget)
    window.resize(1280, 900)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    run_standalone()
