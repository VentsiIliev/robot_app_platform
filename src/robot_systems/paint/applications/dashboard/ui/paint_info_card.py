from __future__ import annotations

import os

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QFrame, QLabel, QToolButton, QVBoxLayout, QWidget

from pl_gui.settings.settings_view.styles import (
    BORDER,
    PRIMARY,
    PRIMARY_DARK,
    SCROLLBAR_HANDLE_HOVER,
    TEXT_COLOR,
)
from pl_gui.shell.ui.icon_loader import load_icon


_STATUS_GOOD = PRIMARY
_STATUS_WARNING = PRIMARY_DARK
_STATUS_UNAVAILABLE = SCROLLBAR_HANDLE_HOVER
_COMPACT_SIZE = 48


_CARD_STYLE = f"""
QWidget {{
    background: white;
    border: 1px solid {BORDER};
    border-radius: 8px;
}}
QLabel {{
    background: transparent;
    border: none;
    color: {TEXT_COLOR};
}}
"""


class PaintInfoCard(QWidget):
    """Operator-facing placeholder card for paint dashboard expo data."""

    expansion_changed = pyqtSignal(bool)

    def __init__(
        self,
        title: str,
        value: str,
        note: str,
        *,
        icon_name: str = "fa5s.circle",
        parent=None,
    ):
        super().__init__(parent)
        self._icon_name = icon_name
        self.setStyleSheet(_CARD_STYLE)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        frame = QFrame()
        frame.setStyleSheet(_CARD_STYLE)
        outer.addWidget(frame)

        layout = QVBoxLayout(frame)
        self._content_layout = layout
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)

        self._indicator = QToolButton()
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._indicator.setAutoRaise(True)
        self._indicator.setFixedSize(36, 36)
        self._indicator.setIconSize(QSize(32, 32))
        self._indicator.setStyleSheet("background: transparent; border: none;")
        self._indicator.hide()

        self._title_label = QLabel(title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._title_label.setStyleSheet(f"font-size: 12pt; font-weight: bold; color: {PRIMARY};")

        self._value_label = QLabel(value)
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value_label.setStyleSheet("font-size: 16pt; font-weight: bold;")

        line = QFrame()
        self._line = line
        line.setFixedHeight(1)
        line.setStyleSheet(f"QFrame {{ background: {BORDER}; border: none; }}")

        layout.addWidget(self._indicator, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)
        layout.addWidget(line)
        layout.addStretch(1)
        layout.addWidget(self._value_label)
        layout.addStretch(1)
        self._compact = False
        self._expanded = False
        self._value = value
        self._note = note
        self._update_indicator(value)

    def set_content(self, title: str, value: str, note: str) -> None:
        self._title_label.setText(title)
        self._value_label.setText(value)
        self._value = value
        self._note = note
        self._update_indicator(value)
        self.setAccessibleName(f"{title}: {value}")

    def set_status_value(self, value: str) -> None:
        """Update semantic color from the untranslated service status."""
        self._update_indicator(value)

    def set_compact(self, compact: bool = True) -> None:
        self._compact = bool(compact)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
            if self._compact
            else Qt.CursorShape.ArrowCursor
        )
        self.set_expanded(False)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded and self._compact)
        self._indicator.setVisible(self._compact)
        self._title_label.setVisible(not self._compact)
        self._line.setVisible(not self._compact)
        self._value_label.setVisible(not self._compact)
        if not self._compact:
            self.setMinimumWidth(0)
            self.setMaximumWidth(16777215)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            return
        self.setFixedSize(_COMPACT_SIZE, _COMPACT_SIZE)
        self._content_layout.setContentsMargins(0, 0, 0, 0)

    def is_expanded(self) -> bool:
        return self._expanded

    def mouseReleaseEvent(self, event) -> None:
        if self._compact and event.button() == Qt.MouseButton.LeftButton:
            self.expansion_changed.emit(not self._expanded)
        super().mouseReleaseEvent(event)

    def _update_indicator(self, value: str) -> None:
        normalized = str(value or "").strip().lower()
        if normalized in {"online", "ready", "idle", "running", "connected"}:
            color = _STATUS_GOOD
        elif normalized in {"paused", "warning", "starting"}:
            color = _STATUS_WARNING
        elif normalized in {"disconnected", "error", "fault", "offline"}:
            color = _STATUS_UNAVAILABLE
        else:
            color = PRIMARY
        self._status_color = color
        if os.path.isfile(self._icon_name):
            icon = self._tinted_file_icon(self._icon_name, color, QSize(32, 32))
        else:
            icon = load_icon(self._icon_name, color=color)
        self._indicator.setIcon(icon)

    @staticmethod
    def _tinted_file_icon(path: str, color: str, size: QSize) -> QIcon:
        """Tint a rasterized SVG while retaining its transparent background."""
        source = QIcon(path).pixmap(size)
        if source.isNull():
            return QIcon()
        tinted = QPixmap(source.size())
        tinted.fill(Qt.GlobalColor.transparent)
        painter = QPainter(tinted)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceIn
        )
        painter.fillRect(tinted.rect(), QColor(color))
        painter.end()
        return QIcon(tinted)
