from typing import List

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from src.applications.pick_and_place_visualizer.service.i_pick_and_place_visualizer_service import PlacedItem

_PALETTE = [
    ("#E3F2FD", "#1565C0"),
    ("#E8F5E9", "#2E7D32"),
    ("#FFF9C4", "#F57F17"),
    ("#FCE4EC", "#B71C1C"),
    ("#F3E5F5", "#6A1B9A"),
    ("#E0F7FA", "#006064"),
]


class PlaneCanvas(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._x_min    = -450.0
        self._x_max    =  350.0
        self._y_min    =  300.0
        self._y_max    =  700.0
        self._spacing  =   30.0
        self._placed:  List[PlacedItem] = []
        self.setMinimumSize(260, 180)

    def set_bounds(self, x_min: float, x_max: float,
                   y_min: float, y_max: float, spacing: float) -> None:
        self._x_min   = x_min
        self._x_max   = x_max
        self._y_min   = y_min
        self._y_max   = y_max
        self._spacing = spacing
        self.update()

    def set_placed(self, items: List[PlacedItem]) -> None:
        self._placed = items
        self.update()

    def clear(self) -> None:
        self._placed = []
        self.update()

    def add_item(self, item) -> None:
        self._placed.append(item)
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        margin = 24

        dw = w - 2 * margin
        dh = h - 2 * margin

        plane_w = self._x_max - self._x_min
        plane_h = self._y_max - self._y_min
        if plane_w <= 0 or plane_h <= 0:
            return

        scale = min(dw / plane_w, dh / plane_h)
        ox = margin + (dw - plane_w * scale) / 2
        oy = margin + (dh - plane_h * scale) / 2

        def sx(rx): return ox + (rx - self._x_min) * scale
        def sy(ry): return oy + (ry - self._y_min) * scale

        # Background
        painter.fillRect(self.rect(), QColor("#F8F8F8"))

        # Plane fill + border
        prect = QRectF(sx(self._x_min), sy(self._y_min),
                       plane_w * scale, plane_h * scale)
        painter.fillRect(prect, QColor("#FFFFFF"))
        painter.setPen(QPen(QColor("#905BA9"), 2))
        painter.drawRect(prect)

        # Placed workpieces
        for i, item in enumerate(self._placed):
            bg_hex, bd_hex = _PALETTE[i % len(_PALETTE)]
            bw = item.width  * scale
            bh = item.height * scale
            rect = QRectF(sx(item.plane_x) - bw / 2,
                          sy(item.plane_y) - bh / 2,
                          bw, bh)
            painter.fillRect(rect, QColor(bg_hex))
            painter.setPen(QPen(QColor(bd_hex), 1.5))
            painter.drawRect(rect)

            # Label
            font_size = max(6, int(min(bw, bh) * 0.22))
            painter.setFont(QFont("Arial", font_size, QFont.Weight.Bold))
            painter.setPen(QPen(QColor(bd_hex), 1))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter,
                             f"G{item.gripper_id}\n{item.workpiece_name}")

        # Title
        painter.setFont(QFont("Arial", 8))
        painter.setPen(QPen(QColor("#888"), 1))
        painter.drawText(margin, margin - 6, "Placement Plane (robot mm)")