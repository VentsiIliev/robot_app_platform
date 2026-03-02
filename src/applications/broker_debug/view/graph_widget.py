import math
from typing import Dict

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics
from PyQt6.QtWidgets import QWidget, QSizePolicy

_BG         = QColor("#F8F9FA")
_NODE_BG    = QColor("#EDE7F6")
_NODE_EDGE  = QColor("#905BA9")
_TEXT       = QColor("#1A1A2E")
_EDGE_COLOR = QColor("#B0A0D0")
_HUB_BG     = QColor("#905BA9")
_HUB_TEXT   = QColor("#FFFFFF")
_BADGE_BG   = QColor("#5B3ED6")
_BADGE_TEXT = QColor("#FFFFFF")


class GraphWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._topic_map: Dict[str, int] = {}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(300)

    def set_topic_map(self, topic_map: Dict[str, int]) -> None:
        self._topic_map = topic_map
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), _BG)

        topics = list(self._topic_map.items())
        if not topics:
            painter.setPen(_TEXT)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No topics")
            painter.end()
            return

        cx, cy = self.width() / 2, self.height() / 2
        hub_r  = 28

        # Draw hub
        painter.setBrush(QBrush(_HUB_BG))
        painter.setPen(QPen(_HUB_BG.darker(120), 1.5))
        painter.drawEllipse(QPointF(cx, cy), hub_r, hub_r)
        painter.setPen(_HUB_TEXT)
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        painter.drawText(
            QRectF(cx - hub_r, cy - hub_r, hub_r * 2, hub_r * 2),
            Qt.AlignmentFlag.AlignCenter, "BROKER"
        )

        # Layout nodes in a circle
        n      = len(topics)
        radius = min(cx, cy) * 0.72
        node_r = 18
        font   = QFont("Arial", 7)
        fm     = QFontMetrics(font)

        for i, (topic, count) in enumerate(topics):
            angle = 2 * math.pi * i / n - math.pi / 2
            nx    = cx + radius * math.cos(angle)
            ny    = cy + radius * math.sin(angle)

            # Edge broker → node
            painter.setPen(QPen(_EDGE_COLOR, 1.2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawLine(QPointF(cx, cy), QPointF(nx, ny))

            # Node circle
            painter.setBrush(QBrush(_NODE_BG))
            painter.setPen(QPen(_NODE_EDGE, 1.5))
            painter.drawEllipse(QPointF(nx, ny), node_r, node_r)

            # Subscriber badge
            if count > 0:
                bx, by = nx + node_r * 0.65, ny - node_r * 0.65
                painter.setBrush(QBrush(_BADGE_BG))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(QPointF(bx, by), 9, 9)
                painter.setPen(_BADGE_TEXT)
                painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
                painter.drawText(
                    QRectF(bx - 9, by - 9, 18, 18),
                    Qt.AlignmentFlag.AlignCenter, str(count)
                )

            # Topic label outside circle
            label_r = node_r + 6
            lx = cx + (radius + label_r) * math.cos(angle)
            ly = cy + (radius + label_r) * math.sin(angle)
            short = topic.split("/")[-1]
            tw    = fm.horizontalAdvance(short)
            painter.setPen(_TEXT)
            painter.setFont(font)
            painter.drawText(
                QRectF(lx - tw / 2 - 4, ly - 8, tw + 8, 16),
                Qt.AlignmentFlag.AlignCenter, short
            )

        painter.end()