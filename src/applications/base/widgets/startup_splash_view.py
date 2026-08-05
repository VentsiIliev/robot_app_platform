from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pl_gui.settings.settings_view.styles import (
    BG_COLOR,
    PRIMARY,
    TERTIARY_TEXT,
)


class StartupSplashView(QWidget):
    """Reusable full-page startup/loading view."""

    _DEFAULT_LOGO_PATH = Path(__file__).resolve().parents[1] / "resources" / "logo.ico"

    def __init__(self, parent: QWidget | None = None, *, logo_path: str | Path | None = None) -> None:
        super().__init__(parent)
        self._active_step = 0
        self._dot_count = 0
        self._message_base = self.tr("Preparing runtime services")
        self._logo_path = Path(logo_path) if logo_path is not None else self._DEFAULT_LOGO_PATH

        self._logo = QLabel()
        self._message = QLabel(self._message_base)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self._build_ui()
        self.set_active_step(0)
        self.set_busy(True)

    def set_title(self, text: str) -> None:
        # Kept for compatibility with the previous card-style splash API.
        return None

    def set_message(self, text: str) -> None:
        self._message_base = str(text or "")
        self._dot_count = 0
        self._message.setText(self._message_base)

    def set_steps(self, steps: list[str]) -> None:
        # Kept for compatibility. This splash presents only the active stage text.
        return None

    def set_active_step(self, index: int) -> None:
        self._active_step = max(0, int(index))

    def mark_complete(self) -> None:
        self.set_message(self.tr("Ready"))
        self.set_busy(False)

    def set_error(self, message: str) -> None:
        self.set_message(message)
        self.set_busy(False)

    def set_busy(self, busy: bool) -> None:
        if busy:
            if not self._timer.isActive():
                self._timer.start(450)
            return
        self._timer.stop()

    def _build_ui(self) -> None:
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet(f"background: {BG_COLOR};")

        root = QVBoxLayout(self)
        root.setContentsMargins(72, 72, 72, 42)
        root.setSpacing(0)
        root.addStretch(1)

        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo.setStyleSheet("background: transparent;")
        pixmap = QPixmap(str(self._logo_path))
        if not pixmap.isNull():
            self._logo.setPixmap(
                pixmap.scaled(
                    380,
                    160,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        else:
            self._logo.setText(self.tr("Robot App Platform"))
            self._logo.setStyleSheet(f"color: {PRIMARY}; font-size: 28pt; font-weight: bold; background: transparent;")
        root.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignCenter)

        root.addStretch(1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch(1)
        self._message.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._message.setMinimumWidth(360)
        self._message.setMinimumHeight(28)
        self._message.setStyleSheet(f"color: {TERTIARY_TEXT}; font-size: 10pt; font-weight: bold; background: transparent;")
        bottom_row.addWidget(self._message)
        root.addLayout(bottom_row)

    def _tick(self) -> None:
        self._dot_count = (self._dot_count + 1) % 4
        self._message.setText(self._message_base + ("." * self._dot_count))
