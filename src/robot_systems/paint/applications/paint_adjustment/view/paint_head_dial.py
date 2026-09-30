from __future__ import annotations

from math import atan2, cos, degrees, hypot, radians, sin

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from pl_gui.settings.settings_view.styles import BORDER, PRIMARY, TERTIARY_TEXT, TEXT_COLOR, TEXT_ON_PRIMARY
from src.robot_systems.paint.applications.paint_adjustment.dial_geometry import (
    dial_angle_for_value,
    dial_setting_for_value,
    dial_value_for_angle,
)


class PaintHeadDial(QWidget):
    """Paint-only visual of evenly spaced presets and register position."""

    drag_started = pyqtSignal()
    position_dragged = pyqtSignal(int)
    position_requested = pyqtSignal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._minimum = 0
        self._spacing = 1
        self._count = 0
        self._actual_value: int | None = None
        self._preview_value: int | None = None
        self._selected_setting: int | None = None
        self._dragging = False
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def configure(self, minimum: int, spacing: int, count: int) -> None:
        self._minimum = minimum
        self._spacing = spacing
        self._count = count
        self._dragging = False
        self._selected_setting = None
        self.update()

    def set_actual(self, value: int | None) -> None:
        self._actual_value = value
        if not self._dragging:
            self._preview_value = None
            self._selected_setting = None
        self.update()

    def set_preview(self, value: int | None) -> None:
        self._preview_value = value
        self._selected_setting = None
        self.update()

    def cancel_drag(self) -> None:
        self._dragging = False
        self._preview_value = None
        self._selected_setting = None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled() or self._count < 1:
            super().mousePressEvent(event)
            return
        value = self._value_at(event.position())
        if value is None:
            return
        self._dragging = True
        self.drag_started.emit()
        self._select_value(value)
        event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            value = self._value_at(event.position())
            if value is not None:
                self._select_value(value)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if not self._dragging or event.button() != Qt.MouseButton.LeftButton:
            super().mouseReleaseEvent(event)
            return
        value = self._value_at(event.position())
        if value is not None:
            self._select_value(value)
        self._dragging = False
        if self._preview_value is not None:
            self.position_requested.emit(self._preview_value)
        event.accept()

    def _value_at(self, point: QPointF) -> int | None:
        dx = point.x() - self.width() / 2
        dy = point.y() - self.height() / 2
        if hypot(dx, dy) < 18:
            return None
        angle = degrees(atan2(dy, dx))
        return dial_value_for_angle(angle, self._minimum, self._spacing, self._count)

    def _select_value(self, value: int) -> None:
        changed = value != self._preview_value
        maximum = self._minimum + self._spacing * (self._count - 1)
        distance = maximum - value
        self._selected_setting = 1 + distance // self._spacing if distance % self._spacing == 0 else None
        self._preview_value = value
        self.update()
        if changed:
            self.position_dragged.emit(value)

    @property
    def actual_value(self) -> int | None:
        return self._actual_value

    @property
    def preview_value(self) -> int | None:
        return self._preview_value

    def format_position(self, value: int) -> str:
        """Display a register value on the setting scale, to one decimal place."""
        if self._count < 1:
            return str(value)
        setting = dial_setting_for_value(value, self._minimum, self._spacing, self._count)
        return f"{setting:.1f}" if setting is not None else str(value)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(TEXT_ON_PRIMARY))
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
            selected = setting == self._selected_setting
            painter.setPen(QPen(QColor(PRIMARY), 2))
            painter.setBrush(QColor(PRIMARY if selected else TEXT_ON_PRIMARY))
            painter.drawEllipse(marker, 9 if selected else 6, 9 if selected else 6)

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

        display_value = self._preview_value if self._preview_value is not None else self._actual_value
        current_text = "—" if display_value is None else self.format_position(display_value)
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
