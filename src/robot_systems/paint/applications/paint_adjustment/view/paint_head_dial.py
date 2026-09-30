from __future__ import annotations

from math import cos, radians, sin

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from pl_gui.settings.settings_view.styles import BG_COLOR, BORDER, PRIMARY, TERTIARY_TEXT, TEXT_COLOR
from src.robot_systems.paint.applications.paint_adjustment.dial_geometry import (
    dial_angle_for_value,
)


class PaintHeadDial(QWidget):
    """Paint-only visual of evenly spaced presets and register position."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._spacing = 1
        self._count = 0
        self._actual_value: int | None = None
        self._preview_value: int | None = None
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def configure(self, minimum: int, spacing: int, count: int) -> None:
        self._minimum = minimum
        self._spacing = spacing
        self._count = count
        self.update()

    def set_actual(self, value: int | None) -> None:
        self._actual_value = value
        self._preview_value = None
        self.update()

    def set_preview(self, value: int | None) -> None:
        self._preview_value = value
        self.update()

    @property
    def actual_value(self) -> int | None:
        return self._actual_value

    @property
    def preview_value(self) -> int | None:
        return self._preview_value

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(BG_COLOR))
        if self._count < 1:
            return

        center = QPointF(self.width() / 2, self.height() / 2)
        radius = max(25.0, min(self.width(), self.height()) / 2 - 42.0)
        painter.setPen(QPen(QColor(BORDER), 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, radius, radius)

        for setting in range(1, self._count + 1):
            value = self._minimum + self._spacing * (self._count - setting)
            angle = dial_angle_for_value(value, self._minimum, self._spacing, self._count)
            marker = self._point(center, radius, angle)
            painter.setPen(QPen(QColor(PRIMARY), 2))
            painter.setBrush(QColor(BG_COLOR))
            painter.drawEllipse(marker, 6, 6)

            label = self._point(center, radius + 22, angle)
            painter.setPen(QColor(TEXT_COLOR))
            text_rect = painter.fontMetrics().boundingRect(str(setting))
            painter.drawText(
                QPointF(label.x() - text_rect.width() / 2, label.y() + text_rect.height() / 3),
                str(setting),
            )

        self._draw_pointer(painter, center, radius, self._actual_value, QColor(PRIMARY), False)
        self._draw_pointer(painter, center, radius, self._preview_value, QColor(TERTIARY_TEXT), True)
        painter.setPen(QPen(QColor(TEXT_COLOR), 1))
        painter.setBrush(QColor(TEXT_COLOR))
        painter.drawEllipse(center, 5, 5)

        current_text = "—" if self._actual_value is None else str(self._actual_value)
        painter.setPen(QColor(TEXT_COLOR))
        text_rect = painter.fontMetrics().boundingRect(current_text)
        painter.drawText(
            QPointF(center.x() - text_rect.width() / 2, center.y() + radius * 0.55),
            current_text,
        )

    def _draw_pointer(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        value: int | None,
        color: QColor,
        dashed: bool,
    ) -> None:
        if value is None:
            return
        angle = dial_angle_for_value(value, self._minimum, self._spacing, self._count)
        if angle is None:
            return
        pen = QPen(color, 4 if not dashed else 2)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(center, self._point(center, radius * 0.76, angle))

    @staticmethod
    def _point(center: QPointF, radius: float, angle: float) -> QPointF:
        theta = radians(angle)
        return QPointF(center.x() + radius * cos(theta), center.y() + radius * sin(theta))
