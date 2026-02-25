import logging

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QFont, QPainter, QPen, QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QLabel, QHBoxLayout

try:
    from src.dashboard.resources.styles import ICON_COLOR, STATUS_UNKNOWN, STATUS_READY, STATUS_ERROR, STATUS_DISCONNECTED
except ImportError:
    try:
        from dashboard.styles import ICON_COLOR, STATUS_UNKNOWN, STATUS_READY, STATUS_ERROR, STATUS_DISCONNECTED
    except ImportError:
        ICON_COLOR = "#905BA9"
        STATUS_UNKNOWN = "#808080"
        STATUS_READY = "#28a745"
        STATUS_ERROR = "#d9534f"
        STATUS_DISCONNECTED = "#6c757d"


class GlueMeterWidget(QWidget):
    def __init__(self, id: int, parent: QWidget = None, capacity_grams: float = 5000.0):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.id = id
        self.glue_percent = 0
        self.glue_grams = 0
        self.max_volume_grams = capacity_grams
        self.setMinimumWidth(250)
        self.setFixedHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.label_container = QWidget()
        self.label_container.setStyleSheet("QWidget { border: none; background: transparent; }")
        label_layout = QVBoxLayout(self.label_container)
        label_layout.setContentsMargins(0, 0, 0, 0)
        label_layout.setSpacing(0)
        self.label = QLabel("0 g")
        self.label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
        self.label.setMinimumWidth(100)
        self.label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.label.setStyleSheet("QLabel { border: none; background: transparent; }")
        font = QFont()
        font.setPointSize(15)
        self.label.setFont(font)
        label_layout.addWidget(self.label)
        self.main_layout.addWidget(self.label_container)
        self.state_container = QWidget()
        self.state_container.setStyleSheet("QWidget { border: none; background: transparent; }")
        state_layout = QVBoxLayout(self.state_container)
        state_layout.setContentsMargins(0, 0, 0, 0)
        state_layout.setSpacing(0)
        self.state_indicator = QLabel()
        self.state_indicator.setFixedSize(16, 16)
        self.state_indicator.setStyleSheet("background-color: gray; border-radius: 8px;")
        self.main_layout.addWidget(self.state_container)
        self.canvas = QWidget()
        self.canvas.setMinimumHeight(50)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.main_layout.addWidget(self.canvas)

    def set_weight(self, grams: float) -> None:
        try:
            if grams is not None:
                percent = (grams / self.max_volume_grams) * 100
                self.setGluePercent(percent, grams)
            else:
                raise ValueError("grams is None")
        except Exception:
            self.setGluePercent(0)
            self.label.setText("N/A")
            self.canvas.update()

    def set_state(self, state: str) -> None:
        try:
            s = str(state).strip().lower()
            if s == "ready":
                self.state_indicator.setStyleSheet(f"background-color: {STATUS_READY}; border-radius: 8px;")
            elif s in ("disconnected", "error"):
                self.state_indicator.setStyleSheet(f"background-color: {STATUS_ERROR}; border-radius: 8px;")
            else:
                self.state_indicator.setStyleSheet(f"background-color: {STATUS_UNKNOWN}; border-radius: 8px;")
        except Exception:
            self.state_indicator.setStyleSheet(f"background-color: {STATUS_UNKNOWN}; border-radius: 8px;")

    def updateWidgets(self, message) -> None:
        self.set_weight(message)

    def updateState(self, message) -> None:
        self.set_state(message if isinstance(message, str) else "unknown")

    def setGluePercent(self, percent, grams=None) -> None:
        self.glue_percent = max(0, min(100, percent))
        if grams is not None:
            self.glue_grams = grams
            try:
                self.label.setText(f"{float(grams):.2f} g")
            except (ValueError, TypeError):
                self.label.setText(f"{grams} g")
            self.label.setMaximumHeight(40)
        self.canvas.update()

    def get_shade(self) -> QColor:
        base = QColor(ICON_COLOR)
        if self.glue_percent <= 20:
            return base.lighter(150)
        elif self.glue_percent <= 50:
            return base.lighter(120)
        elif self.glue_percent <= 80:
            return base
        else:
            return base.darker(120)

    def paintEvent(self, event) -> None:
        pass

    def resizeEvent(self, event) -> None:
        self.canvas.repaint()

    def showEvent(self, event) -> None:
        self.canvas.paintEvent = self.custom_paint_event

    def custom_paint_event(self, event) -> None:
        painter = QPainter(self.canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        full_width = self.canvas.width() - 20
        border_rect = QRect(10, 20, full_width, 20)
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        num_steps = 5
        for i in range(num_steps + 1):
            percent = i * (100 // num_steps)
            x = 10 + int((i * full_width) / num_steps)
            painter.drawLine(x, 18, x, 15)
            painter.drawText(x - 10, 10, f"{percent}%")
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        painter.drawRect(border_rect)
        fill_width = int((self.glue_percent / 100) * border_rect.width())
        fill_rect = QRect(border_rect.left() + 1, border_rect.top() + 1,
                          fill_width, border_rect.height() - 2)
        painter.fillRect(fill_rect, self.get_shade())

